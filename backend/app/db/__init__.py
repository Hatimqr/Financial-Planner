"""Database engine and session management."""
from sqlalchemy import create_engine, event, text
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


def create_triggers():
    """Create database triggers for business logic constraints."""
    with engine.connect() as conn:
        # Create the balance trigger
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_tx_post_balance
            BEFORE UPDATE OF posted ON transactions
            FOR EACH ROW WHEN NEW.posted = 1
            BEGIN
              SELECT CASE WHEN (
                SELECT ROUND(COALESCE(SUM(CASE dr_cr WHEN 'DR' THEN amount ELSE -amount END),0), 6)
                FROM transaction_lines WHERE transaction_id = NEW.id
              ) != 0.0 THEN RAISE(ABORT, 'Unbalanced transaction') END;
            END;
        """))
        
        # Create lot over-close prevention trigger
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS trg_lot_not_overclose
            BEFORE UPDATE OF qty_closed ON lots
            FOR EACH ROW WHEN NEW.qty_closed > OLD.qty_opened
            BEGIN
              SELECT RAISE(ABORT, 'Cannot close more than opened quantity');
            END;
        """))
        
        conn.commit()


def create_tables():
    """Create all tables and triggers. Used for testing and initial setup."""
    Base.metadata.create_all(bind=engine)
    create_triggers()


def drop_tables():
    """Drop all tables. Used for testing cleanup."""
    Base.metadata.drop_all(bind=engine)