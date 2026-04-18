"""Initialize database schema."""

from pathlib import Path

from ledger.db.connection import get_db_manager
from ledger.db.models import Base


def initialize_database():
    """Initialize database tables (no default accounts)."""
    Path("data").mkdir(exist_ok=True)

    db_manager = get_db_manager()
    Base.metadata.create_all(db_manager.engine)

    print("✓ Database tables created")
    print("Database initialized. Add your own accounts to get started.")


if __name__ == "__main__":
    initialize_database()
