"""Database connection management for Ledger TUI."""

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from ledger.db.models import Base


# Enable foreign keys and Write-Ahead Logging for SQLite
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Configure SQLite connection with optimal settings."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


class DatabaseManager:
    """Manages database connections and sessions."""

    def __init__(self, db_path: str = "data/ledger.db"):
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database file (default: data/ledger.db)
        """
        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,  # Set to True for SQL debugging
        )
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions.

        Yields:
            SQLAlchemy Session

        Example:
            with db_manager.get_session() as session:
                account = session.query(Account).first()
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_all_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(self.engine)

    def drop_all_tables(self):
        """Drop all database tables (use with caution!)."""
        Base.metadata.drop_all(self.engine)


# Global database manager instance
_db_manager: DatabaseManager | None = None


def get_db_manager(db_path: str = "data/ledger.db") -> DatabaseManager:
    """
    Get or create the global database manager instance.

    Args:
        db_path: Path to SQLite database file

    Returns:
        DatabaseManager instance
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(db_path)
    return _db_manager
