from contextlib import contextmanager

from app.db.base import SessionLocal


@contextmanager
def get_session():
    """Use as a context manager anywhere outside of a FastAPI request (bot handlers, scheduler jobs)."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_db():
    """FastAPI dependency: `db: Session = Depends(get_db)`."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
