"""
BidVault — FastAPI Backend  (v2 — full-featured)

Features:
  ✅  SQLAlchemy + SQLite (swap DATABASE_URL for Postgres)
  ✅  JWT admin authentication
  ✅  WebSocket real-time bid broadcasting
  ✅  Email notifications (bid confirmed + outbid)
  ✅  Image upload (local or Cloudinary)
"""

import os
import json
from datetime import datetime

from fastapi import (
    FastAPI, HTTPException, Depends,
    WebSocket, WebSocketDisconnect,
    UploadFile, File, Request,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from dotenv import load_dotenv

load_dotenv()   # reads .env file if present

# ── Local imports (order matters for circular-import safety) ──
import backend.database as database
import backend.models as models
import backend.schemas as schemas
from backend.database    import get_db
from backend.auth        import hash_password, verify_password, create_access_token, verify_token
from backend.email_service import send_bid_confirmation, send_outbid_notice
from backend.storage     import save_image

# ── Create DB tables ──────────────────────────────────────────
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="BidVault", version="2.0.0")

# ── Static files (uploaded images) ───────────────────────────
os.makedirs("static/uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ── CORS ──────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ════════════════════════════════════════════════════════════════
# WEBSOCKET MANAGER
# ════════════════════════════════════════════════════════════════
class ConnectionManager:
    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket):
        self._connections.remove(ws)

    async def broadcast(self, payload: dict):
        """Send JSON to all connected clients; silently drop dead sockets."""
        dead = []
        for ws in self._connections:
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.remove(ws)


manager = ConnectionManager()


# ════════════════════════════════════════════════════════════════
# STARTUP — seed default admin & demo items
# ════════════════════════════════════════════════════════════════
@app.on_event("startup")
def seed():
    db = next(get_db())

    # Default admin  (change password via ADMIN_PASSWORD env var)
    if not db.query(models.DBAdmin).filter_by(username="admin").first():
        db.add(models.DBAdmin(
            username        = "admin",
            hashed_password = hash_password(os.getenv("ADMIN_PASSWORD", "admin123")),
        ))

    # Demo auction items (only if table is empty)
    if not db.query(models.DBItem).first():
        from datetime import timedelta
        def end(h): return (datetime.utcnow() + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%S")

        demos = [
            models.DBItem(
                title="Vintage Rolex Submariner 1965",
                description="All-original 1965 Submariner. Remarkable condition, original bracelet.",
                image_url="https://images.unsplash.com/photo-1587836374828-4dbafa94cf0e?w=600",
                starting_price=8000, current_price=8000, end_time=end(24),
            ),
            models.DBItem(
                title="Abstract Oil Painting – 'Blue Horizon'",
                description="36×48 inch original oil by Meera Nair. Certificate of authenticity included.",
                image_url="https://images.unsplash.com/photo-1579541592347-8501c63d9f94?w=600",
                starting_price=1200, current_price=1200, end_time=end(48),
            ),
            models.DBItem(
                title="1957 Gibson Les Paul Goldtop",
                description="All-original P-90 pickups, original case. A legend of rock history.",
                image_url="https://images.unsplash.com/photo-1510915361894-db8b60106cb1?w=600",
                starting_price=45000, current_price=45000, end_time=end(72),
            ),
        ]
        db.add_all(demos)

    db.commit()
    db.close()


# ════════════════════════════════════════════════════════════════
# HELPER
# ════════════════════════════════════════════════════════════════
def to_dict(item: models.DBItem) -> dict:
    return {
        "id":             item.id,
        "title":          item.title,
        "description":    item.description,
        "image_url":      item.image_url or "",
        "starting_price": item.starting_price,
        "current_price":  item.current_price,
        "end_time":       item.end_time,
        "is_active":      item.is_active,
        "bids": [
            {
                "bidder_name":  b.bidder_name,
                "bidder_email": b.bidder_email,
                "amount":       b.amount,
                "timestamp":    b.timestamp,
            }
            for b in sorted(item.bids, key=lambda x: x.timestamp or "")
        ],
    }


# ════════════════════════════════════════════════════════════════
# WEBSOCKET
# ════════════════════════════════════════════════════════════════
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()   # keep-alive; client can send pings
    except WebSocketDisconnect:
        manager.disconnect(ws)


# ════════════════════════════════════════════════════════════════
# AUTH
# ════════════════════════════════════════════════════════════════
@app.post("/auth/login", response_model=schemas.TokenResponse)
def login(req: schemas.LoginRequest, db: Session = Depends(get_db)):
    admin = db.query(models.DBAdmin).filter_by(username=req.username).first()
    if not admin or not verify_password(req.password, admin.hashed_password):
        raise HTTPException(401, detail="Invalid username or password.")
    return {"access_token": create_access_token({"sub": admin.username})}


# ════════════════════════════════════════════════════════════════
# PUBLIC ROUTES
# ════════════════════════════════════════════════════════════════
@app.get("/")
def root():
    return {"message": "BidVault API v2 is running 🔨"}


@app.get("/items")
def get_all_items(db: Session = Depends(get_db)):
    return [to_dict(i) for i in db.query(models.DBItem).all()]


@app.get("/items/{item_id}")
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(models.DBItem).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(404, detail="Item not found.")
    return to_dict(item)


@app.post("/items/{item_id}/bid")
async def place_bid(item_id: int, req: schemas.PlaceBidRequest, db: Session = Depends(get_db)):
    item = db.query(models.DBItem).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(404, detail="Item not found.")
    if not item.is_active:
        raise HTTPException(400, detail="This auction has ended.")

    # Auto-expire if past end_time
    try:
        if datetime.utcnow() > datetime.fromisoformat(item.end_time):
            item.is_active = False
            db.commit()
            raise HTTPException(400, detail="Auction time has expired.")
    except ValueError:
        pass

    if req.amount <= item.current_price:
        raise HTTPException(400, detail=f"Bid must exceed current price of ${item.current_price:,.2f}.")

    # Find previous top bidder (for outbid email)
    prev_top = max(item.bids, key=lambda b: b.amount, default=None)

    # Save bid
    db.add(models.DBBid(
        item_id      = item.id,
        bidder_name  = req.bidder_name,
        bidder_email = req.bidder_email or "",
        amount       = req.amount,
        timestamp    = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
    ))
    item.current_price = req.amount
    db.commit()
    db.refresh(item)

    result = to_dict(item)

    # Broadcast to all WebSocket clients
    await manager.broadcast({"type": "bid_placed", "item": result})

    # Emails — fire and don't crash if SMTP not configured
    if req.bidder_email:
        send_bid_confirmation(req.bidder_email, req.bidder_name, item.title, req.amount)
    if prev_top and prev_top.bidder_email and prev_top.bidder_email != (req.bidder_email or ""):
        send_outbid_notice(prev_top.bidder_email, prev_top.bidder_name, item.title, req.amount)

    return result


# ════════════════════════════════════════════════════════════════
# ADMIN ROUTES  (JWT required)
# ════════════════════════════════════════════════════════════════
@app.post("/admin/upload-image")
async def upload_image(
    request: Request,
    file:    UploadFile = File(...),
    _:       str        = Depends(verify_token),
):
    """Upload an image and return its public URL."""
    url = await save_image(file, str(request.base_url))
    return {"url": url}


@app.post("/admin/items", status_code=201)
async def add_item(
    req: schemas.AddItemRequest,
    db:  Session = Depends(get_db),
    _:   str     = Depends(verify_token),
):
    item = models.DBItem(
        title          = req.title,
        description    = req.description,
        image_url      = req.image_url or "",
        starting_price = req.starting_price,
        current_price  = req.starting_price,
        end_time       = req.end_time,
        is_active      = True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    result = to_dict(item)
    await manager.broadcast({"type": "item_added", "item": result})
    return result


@app.delete("/admin/items/{item_id}")
async def remove_item(
    item_id: int,
    db:      Session = Depends(get_db),
    _:       str     = Depends(verify_token),
):
    item = db.query(models.DBItem).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(404, detail="Item not found.")
    db.delete(item)
    db.commit()
    await manager.broadcast({"type": "item_removed", "item_id": item_id})
    return {"message": f"'{item.title}' removed."}


@app.patch("/admin/items/{item_id}/toggle")
async def toggle_item(
    item_id: int,
    db:      Session = Depends(get_db),
    _:       str     = Depends(verify_token),
):
    item = db.query(models.DBItem).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(404, detail="Item not found.")
    item.is_active = not item.is_active
    db.commit()
    db.refresh(item)
    result = to_dict(item)
    await manager.broadcast({"type": "item_updated", "item": result})
    return {"is_active": item.is_active, "item": result}
