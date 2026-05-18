from pydantic import BaseModel
from typing import Optional, List


# ── Bid ──────────────────────────────────────────────────
class BidSchema(BaseModel):
    bidder_name:  str
    bidder_email: Optional[str] = ""
    amount:       float
    timestamp:    Optional[str] = None

    class Config:
        from_attributes = True


# ── Auction Item ──────────────────────────────────────────
class AuctionItemSchema(BaseModel):
    id:             int
    title:          str
    description:    str
    image_url:      Optional[str] = ""
    starting_price: float
    current_price:  float
    end_time:       str
    is_active:      bool
    bids:           List[BidSchema] = []

    class Config:
        from_attributes = True


# ── Requests ──────────────────────────────────────────────
class AddItemRequest(BaseModel):
    title:          str
    description:    str
    image_url:      Optional[str] = ""
    starting_price: float
    end_time:       str          # ISO string e.g. "2025-06-01T18:00:00"


class PlaceBidRequest(BaseModel):
    bidder_name:  str
    bidder_email: Optional[str] = ""
    amount:       float


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
