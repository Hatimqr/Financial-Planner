"""
Test configuration and fixtures for the financial planning application.
"""

import os
import tempfile
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, enable_foreign_keys


@pytest.fixture(scope="function")
def db_session():
    """
    Create a test database session with in-memory SQLite.
    
    This fixture creates a fresh database for each test function,
    ensuring test isolation.
    """
    # Create in-memory SQLite database for testing
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
        echo=False
    )
    
    # Enable foreign keys for SQLite
    event.listen(engine, "connect", enable_foreign_keys)
    
    # Create sessionmaker
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        # Drop all tables after test
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="session")
def test_data_dir():
    """Create a temporary directory for test data files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment variables."""
    # Set test database URL
    os.environ['DB_URL'] = 'sqlite:///:memory:'
    os.environ['DB_ECHO'] = 'false'
    
    yield
    
    # Cleanup
    if 'DB_URL' in os.environ:
        del os.environ['DB_URL']
    if 'DB_ECHO' in os.environ:
        del os.environ['DB_ECHO']


@pytest.fixture
def sample_accounts(db_session):
    """Create sample accounts for testing."""
    from app.models import Account
    
    accounts = {
        'cash': Account(name="Assets:Cash", type="ASSET", currency="USD"),
        'brokerage': Account(name="Assets:Brokerage", type="ASSET", currency="USD"),
        'ira': Account(name="Assets:IRA", type="ASSET", currency="USD"),
        'dividend_income': Account(name="Income:Dividends", type="INCOME", currency="USD"),
        'capital_gains': Account(name="Income:Capital Gains", type="INCOME", currency="USD"),
        'fees': Account(name="Expenses:Fees", type="EXPENSE", currency="USD")
    }
    
    for account in accounts.values():
        db_session.add(account)
    db_session.flush()
    
    return accounts


@pytest.fixture
def sample_instruments(db_session):
    """Create sample instruments for testing."""
    from app.models import Instrument
    
    instruments = {
        'aapl': Instrument(symbol="AAPL", name="Apple Inc.", type="EQUITY", currency="USD"),
        'msft': Instrument(symbol="MSFT", name="Microsoft Corporation", type="EQUITY", currency="USD"),
        'spy': Instrument(symbol="SPY", name="SPDR S&P 500 ETF", type="ETF", currency="USD"),
        'tsla': Instrument(symbol="TSLA", name="Tesla Inc.", type="EQUITY", currency="USD")
    }
    
    for instrument in instruments.values():
        db_session.add(instrument)
    db_session.flush()
    
    return instruments


@pytest.fixture
def sample_prices(db_session, sample_instruments):
    """Create sample price data for testing."""
    from app.models import Price
    from datetime import date, timedelta
    
    today = date.today()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    
    prices = [
        # AAPL prices
        Price(instrument_id=sample_instruments['aapl'].id, date=week_ago.isoformat(), close=140.00),
        Price(instrument_id=sample_instruments['aapl'].id, date=yesterday.isoformat(), close=150.00),
        Price(instrument_id=sample_instruments['aapl'].id, date=today.isoformat(), close=155.00),
        
        # MSFT prices
        Price(instrument_id=sample_instruments['msft'].id, date=week_ago.isoformat(), close=250.00),
        Price(instrument_id=sample_instruments['msft'].id, date=yesterday.isoformat(), close=260.00),
        Price(instrument_id=sample_instruments['msft'].id, date=today.isoformat(), close=265.00),
        
        # SPY prices
        Price(instrument_id=sample_instruments['spy'].id, date=week_ago.isoformat(), close=400.00),
        Price(instrument_id=sample_instruments['spy'].id, date=yesterday.isoformat(), close=420.00),
        Price(instrument_id=sample_instruments['spy'].id, date=today.isoformat(), close=425.00),
        
        # TSLA prices
        Price(instrument_id=sample_instruments['tsla'].id, date=week_ago.isoformat(), close=200.00),
        Price(instrument_id=sample_instruments['tsla'].id, date=yesterday.isoformat(), close=220.00),
        Price(instrument_id=sample_instruments['tsla'].id, date=today.isoformat(), close=225.00),
    ]
    
    db_session.add_all(prices)
    db_session.flush()
    
    return prices
