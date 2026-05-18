from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base


class DBAdmin(Base):
    __tablename__ = "admins"

    id               = Column(Integer, primary_key=True, index=True)
    username         = Column(String, unique=True, index=True, nullable=False)
    hashed_password  = Column(String, nullable=False)


class DBItem(Base):
    __tablename__ = "items"

    id             = Column(Integer, primary_key=True, index=True)
    title          = Column(String, nullable=False)
    description    = Column(String, nullable=False)
    image_url      = Column(String, default="")
    starting_price = Column(Float, nullable=False)
    current_price  = Column(Float, nullable=False)
    end_time       = Column(String, nullable=False)   # ISO-format UTC string
    is_active      = Column(Boolean, default=True)

    bids = relationship("DBBid", back_populates="item", cascade="all, delete-orphan")


class DBBid(Base):
    __tablename__ = "bids"

    id           = Column(Integer, primary_key=True, index=True)
    item_id      = Column(Integer, ForeignKey("items.id"), nullable=False)
    bidder_name  = Column(String, nullable=False)
    bidder_email = Column(String, default="")
    amount       = Column(Float, nullable=False)
    timestamp    = Column(String, nullable=False)

    item = relationship("DBItem", back_populates="bids")
