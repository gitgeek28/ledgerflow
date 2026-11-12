from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

# prepare_threshold=None: no server-side prepared statements, so the same code is safe behind a transaction-mode
# pooler (Neon's -pooler endpoint / PgBouncer) as well as on a direct connection.
engine = create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=5, max_overflow=5,
                       pool_recycle=300, connect_args={"prepare_threshold": None})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
