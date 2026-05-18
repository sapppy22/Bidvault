"""
Image upload storage.

LOCAL mode (default):
  Files are saved to ./static/uploads/ and served as static files.
  Set USE_CLOUDINARY=false (or leave unset).

CLOUDINARY mode:
  Set these env vars:
    USE_CLOUDINARY=true
    CLOUDINARY_CLOUD_NAME=your_cloud_name
    CLOUDINARY_API_KEY=your_api_key
    CLOUDINARY_API_SECRET=your_api_secret
  Install: pip install cloudinary
"""

import os
import uuid
from fastapi import UploadFile, HTTPException

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_MB                = 5
USE_CLOUDINARY        = os.getenv("USE_CLOUDINARY", "false").lower() == "true"

LOCAL_UPLOAD_DIR = "static/uploads"
os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)


async def save_image(file: UploadFile, base_url: str) -> str:
    """Validate and store an uploaded image. Returns a public URL."""
    # ── Validation ─────────────────────────────────────────
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(400, detail="Only JPEG, PNG, WebP, or GIF images are allowed.")

    contents = await file.read()
    if len(contents) > MAX_MB * 1024 * 1024:
        raise HTTPException(400, detail=f"File exceeds {MAX_MB} MB limit.")

    # ── Cloudinary ─────────────────────────────────────────
    if USE_CLOUDINARY:
        try:
            import cloudinary
            import cloudinary.uploader
            cloudinary.config(
                cloud_name = os.environ["CLOUDINARY_CLOUD_NAME"],
                api_key    = os.environ["CLOUDINARY_API_KEY"],
                api_secret = os.environ["CLOUDINARY_API_SECRET"],
            )
            result = cloudinary.uploader.upload(
                contents,
                folder         = "bidvault",
                resource_type  = "image",
                transformation = [{"width": 1200, "crop": "limit", "quality": "auto"}],
            )
            return result["secure_url"]
        except Exception as exc:
            raise HTTPException(500, detail=f"Cloudinary upload failed: {exc}")

    # ── Local storage ───────────────────────────────────────
    ext      = (file.filename or "image.jpg").rsplit(".", 1)[-1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    path     = os.path.join(LOCAL_UPLOAD_DIR, filename)

    with open(path, "wb") as f:
        f.write(contents)

    return f"{base_url.rstrip('/')}/static/uploads/{filename}"
