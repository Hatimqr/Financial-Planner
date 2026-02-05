"""Pytest fixtures for testing."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ledger.db.models import Base
from ledger.services.account_service import AccountService


@pytest.fixture
def test_engine():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    # Note: No trigger needed - validation is done in service layer

    yield engine

    Base.metadata.drop_all(engine)


@pytest.fixture
def session(test_engine):
    """Create database session for tests."""
    Session = sessionmaker(bind=test_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def sample_accounts(session):
    """Create sample account hierarchy."""
    service = AccountService(session)

    accounts = {
        "assets": service.create_account("Assets", "asset", is_placeholder=True),
        "assets_bank": service.create_account(
            "Assets:Bank", "asset", is_placeholder=True
        ),
        "checking": service.create_account("Assets:Bank:Checking", "asset"),
        "savings": service.create_account("Assets:Bank:Savings", "asset"),
        "expenses": service.create_account("Expenses", "expense", is_placeholder=True),
        "food": service.create_account("Expenses:Food", "expense", is_placeholder=True),
        "groceries": service.create_account("Expenses:Food:Groceries", "expense"),
        "restaurants": service.create_account("Expenses:Food:Restaurants", "expense"),
        "housing": service.create_account("Expenses:Housing", "expense", is_placeholder=True),
        "utilities": service.create_account("Expenses:Housing:Utilities", "expense"),
        "transport": service.create_account("Expenses:Transport", "expense"),
        "income": service.create_account("Income", "income", is_placeholder=True),
        "salary": service.create_account("Income:Salary", "income"),
        "equity": service.create_account("Equity", "equity", is_placeholder=True),
        "opening": service.create_account("Equity:OpeningBalance", "equity"),
        "liabilities": service.create_account(
            "Liabilities", "liability", is_placeholder=True
        ),
        "credit_card": service.create_account("Liabilities:CreditCard", "liability"),
    }

    session.commit()
    return accounts
