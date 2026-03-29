"""Database engine/session setup and request-scoped session dependency."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./rezgian.db"

# check_same_thread is required for SQLite with FastAPI request handling.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator:
    """Yield a database session for a single request lifecycle."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
