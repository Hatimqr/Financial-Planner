"""Test trigger functionality for balance and lot constraints."""
import pytest
import tempfile
import os
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from datetime import date

from app.db import Base, enable_foreign_keys
from app.models import Account, Instrument, Transaction, TransactionLine, Lot


class TestTriggers:
    """Test database triggers."""
    
    @pytest.fixture
    def temp_db_session(self):
        """Create a temporary database session for testing."""
        # Create temporary database file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_file.close()
        
        # Create engine with foreign keys enabled
        engine = create_engine(f'sqlite:///{temp_file.name}', echo=False)
        event.listen(engine, "connect", enable_foreign_keys)
        
        # Create all tables using SQLAlchemy models
        Base.metadata.create_all(engine)
        
        # Add database triggers manually (these are SQLite specific)
        with engine.connect() as conn:
            # Create the balance trigger
            conn.execute(text("""
                CREATE TRIGGER trg_tx_post_balance
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
                CREATE TRIGGER trg_lot_not_overclose
                BEFORE UPDATE OF qty_closed ON lots
                FOR EACH ROW WHEN NEW.qty_closed > OLD.qty_opened
                BEGIN
                  SELECT RAISE(ABORT, 'Lot over-closed');
                END;
            """))
            
            conn.commit()
        
        # Create session
        Session = sessionmaker(bind=engine)
        session = Session()
        
        yield session
        
        # Cleanup
        session.close()
        engine.dispose()
        os.unlink(temp_file.name)
    
    def test_balance_trigger_unbalanced(self, temp_db_session):
        """Test that balance trigger prevents posting unbalanced transactions."""
        session = temp_db_session
        
        # Create test accounts
        cash_account = Account(name="Cash", type="ASSET", currency="USD")
        equity_account = Account(name="Equity", type="EQUITY", currency="USD")
        session.add_all([cash_account, equity_account])
        session.flush()
        
        # Create unbalanced transaction
        transaction = Transaction(
            date=date.today().isoformat(),
            type="ADJUST",
            memo="Test unbalanced",
            posted=0  # Not posted yet
        )
        session.add(transaction)
        session.flush()
        
        # Add only one side (unbalanced)
        line1 = TransactionLine(
            transaction_id=transaction.id,
            account_id=cash_account.id,
            amount=100.00,
            dr_cr="DR"
        )
        session.add(line1)
        session.commit()
        
        # Try to post the unbalanced transaction - should fail
        with pytest.raises(IntegrityError) as exc_info:
            transaction.posted = 1
            session.commit()
        
        assert "Unbalanced transaction" in str(exc_info.value)
    
    def test_balance_trigger_balanced(self, temp_db_session):
        """Test that balance trigger allows posting balanced transactions."""
        session = temp_db_session
        
        # Create test accounts
        cash_account = Account(name="Cash", type="ASSET", currency="USD")
        equity_account = Account(name="Equity", type="EQUITY", currency="USD")
        session.add_all([cash_account, equity_account])
        session.flush()
        
        # Create balanced transaction
        transaction = Transaction(
            date=date.today().isoformat(),
            type="ADJUST",
            memo="Test balanced",
            posted=0
        )
        session.add(transaction)
        session.flush()
        
        # Add balanced lines
        line1 = TransactionLine(
            transaction_id=transaction.id,
            account_id=cash_account.id,
            amount=100.00,
            dr_cr="DR"
        )
        line2 = TransactionLine(
            transaction_id=transaction.id,
            account_id=equity_account.id,
            amount=100.00,
            dr_cr="CR"
        )
        session.add_all([line1, line2])
        session.commit()
        
        # Post the balanced transaction - should succeed
        transaction.posted = 1
        session.commit()
        
        # Verify it was posted
        assert transaction.posted == 1
    
    def test_lot_overclose_trigger(self, temp_db_session):
        """Test that lot over-close trigger prevents closing more than opened."""
        session = temp_db_session
        
        # Create test data
        account = Account(name="Brokerage", type="ASSET", currency="USD")
        instrument = Instrument(symbol="AAPL", name="Apple", type="EQUITY", currency="USD")
        session.add_all([account, instrument])
        session.flush()
        
        # Create lot with 100 shares
        lot = Lot(
            instrument_id=instrument.id,
            account_id=account.id,
            open_date=date.today().isoformat(),
            qty_opened=100.0,
            qty_closed=0.0,
            cost_total=15000.0,
            closed=0
        )
        session.add(lot)
        session.commit()
        
        # Try to close more than opened - should fail
        with pytest.raises(IntegrityError) as exc_info:
            lot.qty_closed = 150.0  # More than the 100 opened
            session.commit()
        
        assert "Lot over-closed" in str(exc_info.value)
    
    def test_lot_normal_close(self, temp_db_session):
        """Test that lot can be closed normally within opened quantity."""
        session = temp_db_session
        
        # Create test data
        account = Account(name="Brokerage", type="ASSET", currency="USD")
        instrument = Instrument(symbol="AAPL", name="Apple", type="EQUITY", currency="USD")
        session.add_all([account, instrument])
        session.flush()
        
        # Create lot with 100 shares
        lot = Lot(
            instrument_id=instrument.id,
            account_id=account.id,
            open_date=date.today().isoformat(),
            qty_opened=100.0,
            qty_closed=0.0,
            cost_total=15000.0,
            closed=0
        )
        session.add(lot)
        session.commit()
        
        # Close 50 shares - should succeed
        lot.qty_closed = 50.0
        session.commit()
        
        # Verify the change
        assert lot.qty_closed == 50.0
        
        # Close the remaining 50 shares - should succeed
        lot.qty_closed = 100.0
        lot.closed = 1
        session.commit()
        
        # Verify fully closed
        assert lot.qty_closed == 100.0
        assert lot.closed == 1
    
    def test_balance_trigger_rounding(self, temp_db_session):
        """Test balance trigger handles floating point rounding correctly."""
        session = temp_db_session
        
        # Create test accounts
        cash_account = Account(name="Cash", type="ASSET", currency="USD")
        equity_account = Account(name="Equity", type="EQUITY", currency="USD")
        session.add_all([cash_account, equity_account])
        session.flush()
        
        # Create transaction with amounts that might have rounding issues
        transaction = Transaction(
            date=date.today().isoformat(),
            type="ADJUST",
            memo="Test rounding",
            posted=0
        )
        session.add(transaction)
        session.flush()
        
        # Add lines with amounts that sum to near-zero due to floating point
        line1 = TransactionLine(
            transaction_id=transaction.id,
            account_id=cash_account.id,
            amount=100.1,
            dr_cr="DR"
        )
        line2 = TransactionLine(
            transaction_id=transaction.id,
            account_id=equity_account.id,
            amount=100.1,
            dr_cr="CR"
        )
        session.add_all([line1, line2])
        session.commit()
        
        # Post the transaction - should succeed due to rounding to 6 decimal places
        transaction.posted = 1
        session.commit()
        
        assert transaction.posted == 1