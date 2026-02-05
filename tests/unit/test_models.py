"""Tests for database models."""

import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy.exc import IntegrityError

from ledger.db.models import Account, Entry, Posting


def test_account_creation(session):
    """Test account model creation."""
    account = Account(
        name="Assets:Cash",
        type="asset",
        currency="USD",
        is_placeholder=False,
    )
    session.add(account)
    session.commit()

    assert account.id is not None
    assert account.name == "Assets:Cash"
    assert account.type == "asset"
    assert account.currency == "USD"
    assert account.is_placeholder is False
    assert account.created_at is not None


def test_account_unique_name_constraint(session):
    """Test that account names must be unique."""
    account1 = Account(name="Assets:Test", type="asset", currency="USD")
    session.add(account1)
    session.commit()

    account2 = Account(name="Assets:Test", type="asset", currency="USD")
    session.add(account2)

    with pytest.raises(IntegrityError):
        session.commit()


def test_account_type_constraint(session):
    """Test that account type must be valid."""
    account = Account(name="Test", type="invalid_type", currency="USD")
    session.add(account)

    with pytest.raises(Exception):  # CheckConstraint violation
        session.commit()


def test_entry_creation(session):
    """Test entry model creation."""
    entry = Entry(
        date=date.today(),
        description="Test transaction",
        payee="Test Payee",
        status="cleared",
    )
    session.add(entry)
    session.commit()

    assert entry.id is not None
    assert entry.description == "Test transaction"
    assert entry.payee == "Test Payee"
    assert entry.status == "cleared"
    assert entry.created_at is not None


def test_entry_status_constraint(session):
    """Test that entry status must be valid."""
    entry = Entry(
        date=date.today(),
        description="Test",
        status="invalid_status",
    )
    session.add(entry)

    with pytest.raises(Exception):  # CheckConstraint violation
        session.commit()


def test_posting_creation(session, sample_accounts):
    """Test posting model creation."""
    entry = Entry(
        date=date.today(),
        description="Test transaction",
        status="cleared",
    )
    session.add(entry)
    session.flush()

    posting = Posting(
        entry_id=entry.id,
        account_id=sample_accounts["checking"].id,
        amount=Decimal("100.00"),
        memo="Test memo",
    )
    session.add(posting)
    session.flush()

    assert posting.id is not None
    assert posting.entry_id == entry.id
    assert posting.account_id == sample_accounts["checking"].id
    assert posting.amount == Decimal("100.00")
    assert posting.memo == "Test memo"


def test_posting_cascade_delete(session, sample_accounts):
    """Test that postings are deleted when entry is deleted."""
    entry = Entry(
        date=date.today(),
        description="Test transaction",
        status="cleared",
    )
    session.add(entry)
    session.flush()

    posting = Posting(
        entry_id=entry.id,
        account_id=sample_accounts["checking"].id,
        amount=Decimal("100.00"),
    )
    session.add(posting)
    session.commit()

    # Delete entry
    session.delete(entry)
    session.commit()

    # Posting should be deleted
    assert session.query(Posting).count() == 0


def test_account_postings_relationship(session, sample_accounts):
    """Test account-posting relationship."""
    entry = Entry(date=date.today(), description="Test", status="cleared")
    session.add(entry)
    session.flush()

    posting = Posting(
        entry_id=entry.id,
        account_id=sample_accounts["checking"].id,
        amount=Decimal("100.00"),
    )
    session.add(posting)
    session.commit()

    # Reload account
    account = session.query(Account).filter_by(id=sample_accounts["checking"].id).first()
    assert len(account.postings) == 1
    assert account.postings[0].amount == Decimal("100.00")


def test_entry_postings_relationship(session, sample_accounts):
    """Test entry-posting relationship."""
    entry = Entry(date=date.today(), description="Test", status="cleared")
    session.add(entry)
    session.flush()

    posting1 = Posting(
        entry_id=entry.id,
        account_id=sample_accounts["checking"].id,
        amount=Decimal("100.00"),
    )
    posting2 = Posting(
        entry_id=entry.id,
        account_id=sample_accounts["groceries"].id,
        amount=Decimal("-100.00"),
    )
    session.add_all([posting1, posting2])
    session.commit()

    # Reload entry
    entry_reloaded = session.query(Entry).filter_by(id=entry.id).first()
    assert len(entry_reloaded.postings) == 2
