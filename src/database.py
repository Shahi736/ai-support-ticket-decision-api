
import os
from datetime import datetime
 
from dotenv import load_dotenv
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text, DateTime, ForeignKey
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
 
load_dotenv()
 
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
 
# check_same_thread=False is needed because FastAPI can use SQLite across threads
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
 
Base = declarative_base()
 
 
class User(Base):
    __tablename__ = "users"
 
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
 
    tickets = relationship("Ticket", back_populates="owner")
 
 
class Ticket(Base):
    __tablename__ = "tickets"
 
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
 
    owner = relationship("User", back_populates="tickets")
    decision = relationship(
        "Decision", back_populates="ticket", uselist=False
    )
 
 
class Decision(Base):
    __tablename__ = "decisions"
 
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    action = Column(String, nullable=False)
    reason = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    sources = Column(Text, nullable=False)  # stored as JSON string
    created_at = Column(DateTime, default=datetime.utcnow)
 
    ticket = relationship("Ticket", back_populates="decision")
 
 
def init_db():
    """Create all tables. Call once on app startup."""
    Base.metadata.create_all(bind=engine)
 
 
def get_db():
    """FastAPI dependency that yields a DB session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
 
