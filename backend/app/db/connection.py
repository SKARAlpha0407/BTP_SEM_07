import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://shreyaskumarrai@localhost:5432/research"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(
    bind=engine, class_=Session, autocommit=False, autoflush=False, expire_on_commit=False
)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
