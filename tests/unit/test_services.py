"""Tests for service layer."""

import pytest
from datetime import date
from decimal import Decimal

from ledger.services.account_service import AccountService
from ledger.services.transaction_service import TransactionService


class TestAccountService:
    """Tests for AccountService."""

    def test_create_account_basic(self, session):
        """Test creating a basic account."""
        service = AccountService(session)
        account = service.create_account("Assets:Test", "asset")

        assert account.name == "Assets:Test"
        assert account.type == "asset"
        assert account.currency == "USD"

    def test_create_account_with_auto_parent(self, session):
        """Test that parent accounts are auto-created."""
        service = AccountService(session)
        child = service.create_account("Assets:Bank:Test:Checking", "asset")

        # Parents should exist
        parent1 = service.get_account_by_name("Assets:Bank")
        parent2 = service.get_account_by_name("Assets:Bank:Test")

        assert parent1 is not None
        assert parent1.is_placeholder is True
        assert parent2 is not None
        assert parent2.is_placeholder is True

    def test_create_account_duplicate_name_fails(self, session, sample_accounts):
        """Test that creating account with duplicate name fails."""
        service = AccountService(session)

        with pytest.raises(ValueError, match="already exists"):
            service.create_account("Assets:Bank:Checking", "asset")

    def test_create_account_invalid_type_fails(self, session):
        """Test that invalid account type fails."""
        service = AccountService(session)

        with pytest.raises(ValueError, match="Invalid account type"):
            service.create_account("Test", "invalid_type")

    def test_get_account_tree(self, session, sample_accounts):
        """Test getting account tree."""
        service = AccountService(session)
        accounts = service.get_account_tree()

        assert len(accounts) > 0
        # Should be sorted by name
        names = [acc.name for acc in accounts]
        assert names == sorted(names)

    def test_get_accounts_by_type(self, session, sample_accounts):
        """Test getting accounts by type."""
        service = AccountService(session)
        assets = service.get_accounts_by_type("asset")

        assert len(assets) > 0
        for acc in assets:
            assert acc.type == "asset"

    def test_archive_account(self, session, sample_accounts):
        """Test archiving an account."""
        service = AccountService(session)
        archived = service.archive_account(sample_accounts["checking"].id)

        assert archived.archived_at is not None

    def test_update_account(self, session, sample_accounts):
        """Test updating account properties."""
        service = AccountService(session)
        updated = service.update_account(
            sample_accounts["checking"].id,
            name="Assets:Bank:MainChecking",
            notes="Updated notes",
        )

        assert updated.name == "Assets:Bank:MainChecking"
        assert updated.notes == "Updated notes"


class TestTransactionService:
    """Tests for TransactionService."""

    def test_create_simple_transaction(self, session, sample_accounts):
        """Test creating a simple two-account transaction."""
        service = TransactionService(session)

        entry = service.create_simple_transaction(
            transaction_date=date.today(),
            description="Test transaction",
            from_account_id=sample_accounts["checking"].id,
            to_account_id=sample_accounts["groceries"].id,
            amount=Decimal("50.00"),
            payee="Store",
            memo="Test memo",
        )

        assert entry.id is not None
        assert len(entry.postings) == 2
        # FROM checking (gets -50), TO groceries (gets +50)
        assert entry.postings[0].amount == Decimal("-50.00")
        assert entry.postings[1].amount == Decimal("50.00")

    def test_create_transaction_negative_amount_fails(self, session, sample_accounts):
        """Test that negative amount fails."""
        service = TransactionService(session)

        with pytest.raises(ValueError, match="Amount must be positive"):
            service.create_simple_transaction(
                transaction_date=date.today(),
                description="Test",
                from_account_id=sample_accounts["checking"].id,
                to_account_id=sample_accounts["groceries"].id,
                amount=Decimal("-50.00"),
            )

    def test_create_transaction_invalid_account_fails(self, session, sample_accounts):
        """Test that invalid account ID fails."""
        service = TransactionService(session)

        with pytest.raises(ValueError, match="not found"):
            service.create_simple_transaction(
                transaction_date=date.today(),
                description="Test",
                from_account_id=99999,  # Non-existent ID
                to_account_id=sample_accounts["groceries"].id,
                amount=Decimal("50.00"),
            )

    def test_create_transaction_same_account_fails(self, session, sample_accounts):
        """Test that transaction with same from/to account fails."""
        service = TransactionService(session)

        with pytest.raises(ValueError, match="cannot be the same"):
            service.create_simple_transaction(
                transaction_date=date.today(),
                description="Test",
                from_account_id=sample_accounts["checking"].id,
                to_account_id=sample_accounts["checking"].id,
                amount=Decimal("50.00"),
            )

    def test_create_multi_split_transaction(self, session, sample_accounts):
        """Test creating a multi-split transaction."""
        service = TransactionService(session)

        postings = [
            (sample_accounts["checking"].id, Decimal("100.00"), "Debit"),
            (sample_accounts["groceries"].id, Decimal("-60.00"), "Food"),
            (sample_accounts["restaurants"].id, Decimal("-40.00"), "Dining"),
        ]

        entry = service.create_multi_split_transaction(
            transaction_date=date.today(),
            description="Split transaction",
            postings=postings,
            payee="Multiple",
        )

        assert entry.id is not None
        assert len(entry.postings) == 3

    def test_create_unbalanced_multi_split_fails(self, session, sample_accounts):
        """Test that unbalanced multi-split fails."""
        service = TransactionService(session)

        postings = [
            (sample_accounts["checking"].id, Decimal("100.00"), None),
            (sample_accounts["groceries"].id, Decimal("-50.00"), None),
            # Missing -50.00, total != 0
        ]

        with pytest.raises(ValueError, match="does not balance"):
            service.create_multi_split_transaction(
                transaction_date=date.today(),
                description="Unbalanced",
                postings=postings,
            )

    def test_get_transactions_by_account(self, session, sample_accounts):
        """Test getting transactions by account."""
        service = TransactionService(session)

        # Create transaction
        service.create_simple_transaction(
            transaction_date=date.today(),
            description="Test",
            from_account_id=sample_accounts["checking"].id,
            to_account_id=sample_accounts["groceries"].id,
            amount=Decimal("50.00"),
        )
        session.commit()

        transactions = service.get_transactions_by_account(sample_accounts["checking"].id)
        assert len(transactions) >= 1

    def test_delete_transaction(self, session, sample_accounts):
        """Test deleting a transaction."""
        service = TransactionService(session)

        entry = service.create_simple_transaction(
            transaction_date=date.today(),
            description="Test",
            from_account_id=sample_accounts["checking"].id,
            to_account_id=sample_accounts["groceries"].id,
            amount=Decimal("50.00"),
        )
        session.commit()

        entry_id = entry.id
        service.delete_transaction(entry_id)
        session.commit()

        assert service.get_transaction_by_id(entry_id) is None
