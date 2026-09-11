from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

# SQLite refuses cross-thread connection sharing by default, which breaks
# FastAPI's threadpool. Postgres needs no such accommodation.
is_sqlite = settings.database_url.startswith("sqlite")

connect_args = {"check_same_thread": False} if is_sqlite else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    # Managed Postgres that scales to zero drops idle connections, so a pooled
    # connection can be dead by the time the next request arrives. Pre-ping
    # costs a round trip and turns that into a transparent reconnect instead of
    # an error in the middle of a phone call. Meaningless for SQLite.
    pool_pre_ping=not is_sqlite,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables if absent.

    Deliberately no migration tool: the schema is defined once and never
    evolves within the scope of this project, so Alembic would be ceremony
    without payoff. A longer-lived service would want migrations here.
    """
    from app import models  # noqa: F401  - registers mappers before create_all

    Base.metadata.create_all(engine)
