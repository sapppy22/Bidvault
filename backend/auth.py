import os
from datetime import datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

# ── Config ────────────────────────────────────────────────
SECRET_KEY  = os.getenv("SECRET_KEY", "change-me-in-production-use-a-long-random-string")
ALGORITHM   = "HS256"
TOKEN_HOURS = 8

pwd_context   = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


# ── Password helpers ──────────────────────────────────────
def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Token helpers ─────────────────────────────────────────
def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(hours=TOKEN_HOURS)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str = Depends(oauth2_scheme)) -> str:
    """FastAPI dependency — call as `_=Depends(verify_token)` on protected routes."""
    try:
        payload  = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token payload.")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Token is invalid or has expired.")
