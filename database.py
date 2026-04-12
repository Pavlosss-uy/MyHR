from sqlalchemy import create_engine, Column, String, JSON, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.mutable import MutableDict
import os
import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# --- THE ULTIMATE SERVERLESS CONFIGURATION ---
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,       # Check if connection is alive before using
    pool_recycle=300,         # Refresh connections every 5 minutes
    connect_args={
        "keepalives": 1,          # Turn on heartbeats
        "keepalives_idle": 10,    # Send heartbeat after 10 seconds of silence
        "keepalives_interval": 5, # Send a heartbeat every 5 seconds after that
        "keepalives_count": 5,    # Try 5 times before giving up
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- DATABASE MODELS ---
class SessionRecord(Base):
    __tablename__ = "sessions"
    session_id = Column(String, primary_key=True, index=True)
    # MutableDict ensures SQLAlchemy tracks in-place dict mutations.
    # Without this, reassigning the same dict object is invisible to the ORM
    # and changes to nested keys (consecutive_fails, question_number, etc.) are lost.
    state_data = Column(MutableDict.as_mutable(JSON), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

# Ensure tables are created
Base.metadata.create_all(bind=engine)

# --- DEPENDENCY INJECTION ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()