# app/db/client.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.db.models import Base
import os

def get_engine():
    if settings.APP_ENV == "production":
        return create_engine(settings.DATABASE_URL, pool_pre_ping=True)

    # modo desarrollo → fallback a SQLite local
    sqlite_path = os.path.join(os.getcwd(), "local_dev.sqlite")
    return create_engine(f"sqlite:///{sqlite_path}", connect_args={"check_same_thread": False})

engine = get_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def init_db():
    Base.metadata.create_all(engine)

def get_session():
    return SessionLocal()
