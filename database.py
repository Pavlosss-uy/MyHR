import os
from sqlalchemy import create_engine, Column, String, JSON, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
from dotenv import load_dotenv

load_dotenv()

# Example: postgresql://user:password@localhost/myhr
DATABASE_URL = os.getenv("DATABASE_URL") 

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class SessionRecord(Base):
    __tablename__ = "sessions"
    
    session_id = Column(String, primary_key=True, index=True)
    state_data = Column(JSON) # We store the entire LangGraph state here
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# Create tables
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()