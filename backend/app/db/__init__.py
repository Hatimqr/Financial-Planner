"""Database engine and session management."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker


def get_database_url() -> str:
    """Get database URL for development."""
    return 'sqlite:///./data/app.db'


def enable_foreign_keys(dbapi_connection, connection_record):
    """Enable foreign key constraints for SQLite connections."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Create engine with foreign key support
engine = create_engine(
    get_database_url(),
    connect_args={"check_same_thread": False},
    echo=False  # Set to True for SQL debugging if needed
)

# Enable foreign keys for SQLite
event.listen(engine, "connect", enable_foreign_keys)

# Create sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base
Base = declarative_base()


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables. Used for testing and initial setup."""
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """Drop all tables. Used for testing cleanup."""
    Base.metadata.drop_all(bind=engine)