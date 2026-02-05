"""Tests for repository layer."""

import pytest
from decimal import Decimal
from datetime import date, timedelta

from ledger.repositories.account import AccountRepository
from ledger.repositories.entry import EntryRepository
from ledger.repositories.posting import PostingRepository
from ledger.db.models import Entry, Posting


def test_account_repo_create(session):
    """Test creating an account via repository."""
    repo = AccountRepository(session)
    account = repo.create(name="Test:Account", type="asset", currency="USD")

    assert account.id is not None
    assert account.name == "Test:Account"
    assert account.type == "asset"


def test_account_repo_get_by_name(session, sample_accounts):
    """Test getting account by name."""
    repo = AccountRepository(session)
    account = repo.get_by_name("Assets:Bank:Checking")

    assert account is not None
    assert account.id == sample_accounts["checking"].id


def test_account_repo_get_active_accounts(session, sample_accounts):
    """Test getting active (non-archived) accounts."""
    repo = AccountRepository(session)

    # Archive one account
    repo.archive(sample_accounts["checking"])
    session.commit()

    active = repo.get_active_accounts()
    archived_ids = [acc.id for acc in active]

    assert sample_accounts["checking"].id not in archived_ids
    assert sample_accounts["savings"].id in archived_ids


def test_account_repo_get_by_type(session, sample_accounts):
    """Test getting accounts by type."""
    repo = AccountRepository(session)
    assets = repo.get_by_type("asset")

    asset_ids = [acc.id for acc in assets]
    assert sample_accounts["checking"].id in asset_ids
    assert sample_accounts["salary"].id not in asset_ids


def test_account_repo_get_children(session, sample_accounts):
    """Test getting child accounts."""
    repo = AccountRepository(session)
    children = repo.get_children("Assets:Bank")

    child_names = [acc.name for acc in children]
    assert "Assets:Bank:Checking" in child_names
    assert "Assets:Bank:Savings" in child_names


def test_entry_repo_get_with_postings(session, sample_accounts):
    """Test getting entry with postings loaded."""
    # Create entry with postings
    entry = Entry(date=date.today(), description="Test", status="cleared")
    session.add(entry)
    session.flush()

    posting1 = Posting(
        entry_id=entry.id,
        account_id=sample_accounts["checking"].id,
        amount=Decimal("100"),
    )
    posting2 = Posting(
        entry_id=entry.id,
        account_id=sample_accounts["groceries"].id,
        amount=Decimal("-100"),
    )
    session.add_all([posting1, posting2])
    session.commit()

    repo = EntryRepository(session)
    loaded_entry = repo.get_with_postings(entry.id)

    assert loaded_entry is not None
    assert len(loaded_entry.postings) == 2


def test_entry_repo_get_by_date_range(session, sample_accounts):
    """Test getting entries by date range."""
    repo = EntryRepository(session)

    # Create entries on different dates
    today = date.today()
    entry1 = Entry(date=today - timedelta(days=10), description="Old", status="cleared")
    entry2 = Entry(date=today, description="Recent", status="cleared")
    entry3 = Entry(date=today + timedelta(days=10), description="Future", status="cleared")

    session.add_all([entry1, entry2, entry3])
    session.commit()

    entries = repo.get_by_date_range(today - timedelta(days=5), today + timedelta(days=5))

    descriptions = [e.description for e in entries]
    assert "Recent" in descriptions
    # "Future" is at today+10, which is outside the range (today+5)
    assert "Future" not in descriptions
    assert "Old" not in descriptions


def test_posting_repo_get_account_balance(session, sample_accounts):
    """Test calculating account balance."""
    # Create transactions
    entry = Entry(date=date.today(), description="Test", status="cleared")
    session.add(entry)
    session.flush()

    posting1 = Posting(
        entry_id=entry.id,
        account_id=sample_accounts["checking"].id,
        amount=Decimal("100"),
    )
    posting2 = Posting(
        entry_id=entry.id,
        account_id=sample_accounts["groceries"].id,
        amount=Decimal("-100"),
    )
    session.add_all([posting1, posting2])
    session.commit()

    repo = PostingRepository(session)
    balance = repo.get_account_balance(sample_accounts["checking"].id)

    assert balance == Decimal("100")


def test_posting_repo_validate_entry_balance(session, sample_accounts):
    """Test validating entry balance."""
    # Create balanced entry
    entry = Entry(date=date.today(), description="Test", status="cleared")
    session.add(entry)
    session.flush()

    posting1 = Posting(
        entry_id=entry.id,
        account_id=sample_accounts["checking"].id,
        amount=Decimal("100"),
    )
    posting2 = Posting(
        entry_id=entry.id,
        account_id=sample_accounts["groceries"].id,
        amount=Decimal("-100"),
    )
    session.add_all([posting1, posting2])
    session.commit()

    repo = PostingRepository(session)
    is_balanced = repo.validate_entry_balance(entry.id)

    assert is_balanced is True
