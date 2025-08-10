"""Test prices table primary key constraints."""
import pytest
import tempfile
import os
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from datetime import date

from app.db import enable_foreign_keys
from app.models import Instrument, Price


class TestPricesPrimaryKey:
    """Test prices table composite primary key constraints."""
    
    @pytest.fixture
    def temp_db_session(self):
        """Create a temporary database session for testing."""
        # Create temporary database file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_file.close()
        
        # Create engine with foreign keys enabled
        engine = create_engine(f'sqlite:///{temp_file.name}', echo=False)
        event.listen(engine, "connect", enable_foreign_keys)
        
        # Create tables manually
        with engine.connect() as conn:
            # Enable foreign keys
            conn.execute(text("PRAGMA foreign_keys = ON;"))
            
            # Create instruments table
            conn.execute(text("""
                CREATE TABLE instruments (
                  id INTEGER PRIMARY KEY,
                  symbol TEXT NOT NULL UNIQUE,
                  name TEXT NOT NULL,
                  type TEXT NOT NULL CHECK (type IN ('EQUITY','ETF','BOND','CASH','CRYPTO')),
                  currency TEXT NOT NULL
                );
            """))
            
            # Create prices table with composite primary key
            conn.execute(text("""
                CREATE TABLE prices (
                  instrument_id INTEGER NOT NULL REFERENCES instruments(id) ON DELETE CASCADE,
                  date TEXT NOT NULL,
                  close REAL NOT NULL,
                  PRIMARY KEY (instrument_id, date)
                );
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
    
    def test_prices_primary_key_constraint(self, temp_db_session):
        """Test that duplicate (instrument_id, date) pairs are prevented."""
        session = temp_db_session
        
        # Create test instrument
        instrument = Instrument(
            symbol="AAPL",
            name="Apple Inc.",
            type="EQUITY",
            currency="USD"
        )
        session.add(instrument)
        session.flush()
        
        today = date.today().isoformat()
        
        # Add first price entry
        price1 = Price(
            instrument_id=instrument.id,
            date=today,
            close=150.00
        )
        session.add(price1)
        session.commit()
        
        # Try to add duplicate (instrument_id, date) - should fail
        with pytest.raises(IntegrityError) as exc_info:
            price2 = Price(
                instrument_id=instrument.id,
                date=today,
                close=155.00  # Different price, but same instrument and date
            )
            session.add(price2)
            session.commit()
        
        # Should mention PRIMARY KEY constraint
        assert "PRIMARY KEY" in str(exc_info.value) or "UNIQUE" in str(exc_info.value)
    
    def test_prices_different_dates_allowed(self, temp_db_session):
        """Test that same instrument can have prices on different dates."""
        session = temp_db_session
        
        # Create test instrument
        instrument = Instrument(
            symbol="AAPL",
            name="Apple Inc.",
            type="EQUITY",
            currency="USD"
        )
        session.add(instrument)
        session.flush()
        
        # Add price for today
        today = date.today().isoformat()
        price1 = Price(
            instrument_id=instrument.id,
            date=today,
            close=150.00
        )
        session.add(price1)
        
        # Add price for different date - should succeed
        different_date = "2024-01-01"
        price2 = Price(
            instrument_id=instrument.id,
            date=different_date,
            close=140.00
        )
        session.add(price2)
        session.commit()
        
        # Verify both prices exist
        prices = session.query(Price).filter_by(instrument_id=instrument.id).all()
        assert len(prices) == 2
        
        price_dates = [p.date for p in prices]
        assert today in price_dates
        assert different_date in price_dates
    
    def test_prices_different_instruments_same_date(self, temp_db_session):
        """Test that different instruments can have prices on same date."""
        session = temp_db_session
        
        # Create test instruments
        aapl = Instrument(
            symbol="AAPL",
            name="Apple Inc.",
            type="EQUITY",
            currency="USD"
        )
        spy = Instrument(
            symbol="SPY",
            name="SPDR S&P 500 ETF",
            type="ETF",
            currency="USD"
        )
        session.add_all([aapl, spy])
        session.flush()
        
        today = date.today().isoformat()
        
        # Add price for AAPL
        price1 = Price(
            instrument_id=aapl.id,
            date=today,
            close=150.00
        )
        
        # Add price for SPY on same date - should succeed
        price2 = Price(
            instrument_id=spy.id,
            date=today,
            close=430.00
        )
        
        session.add_all([price1, price2])
        session.commit()
        
        # Verify both prices exist
        all_prices = session.query(Price).filter_by(date=today).all()
        assert len(all_prices) == 2
        
        instrument_ids = [p.instrument_id for p in all_prices]
        assert aapl.id in instrument_ids
        assert spy.id in instrument_ids
    
    def test_prices_foreign_key_constraint(self, temp_db_session):
        """Test that prices table enforces foreign key to instruments."""
        session = temp_db_session
        
        today = date.today().isoformat()
        
        # Try to add price with non-existent instrument_id
        with pytest.raises(IntegrityError) as exc_info:
            price = Price(
                instrument_id=99999,  # Non-existent instrument
                date=today,
                close=100.00
            )
            session.add(price)
            session.commit()
        
        # Should mention foreign key constraint
        assert "FOREIGN KEY" in str(exc_info.value)
    
    def test_prices_cascade_delete(self, temp_db_session):
        """Test that prices are deleted when instrument is deleted (CASCADE)."""
        session = temp_db_session
        
        # Create test instrument
        instrument = Instrument(
            symbol="AAPL",
            name="Apple Inc.",
            type="EQUITY",
            currency="USD"
        )
        session.add(instrument)
        session.flush()
        
        # Add prices for the instrument
        price1 = Price(
            instrument_id=instrument.id,
            date="2024-01-01",
            close=150.00
        )
        price2 = Price(
            instrument_id=instrument.id,
            date="2024-01-02",
            close=155.00
        )
        session.add_all([price1, price2])
        session.commit()
        
        # Verify prices exist
        prices_before = session.query(Price).filter_by(instrument_id=instrument.id).all()
        assert len(prices_before) == 2
        
        # Delete the instrument
        session.delete(instrument)
        session.commit()
        
        # Verify prices were cascaded deleted
        prices_after = session.query(Price).filter_by(instrument_id=instrument.id).all()
        assert len(prices_after) == 0