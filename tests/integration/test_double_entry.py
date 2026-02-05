"""Integration tests for double-entry accounting rules."""

import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy.exc import IntegrityError

from ledger.db.models import Entry, Posting
from ledger.services.account_service import AccountService
from ledger.services.transaction_service import TransactionService
from ledger.repositories.posting import PostingRepository


def test_balanced_transaction_succeeds(session, sample_accounts):
    """Test that balanced transactions are accepted."""
    entry = Entry(date=date.today(), description="Balanced", status="cleared")
    session.add(entry)
    session.flush()

    # Create balanced postings
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

    # Should not raise exception
    session.flush()
    session.commit()

    assert entry.id is not None


def test_unbalanced_transaction_fails(session, sample_accounts):
    """Test that unbalanced multi-split transactions are rejected by service layer."""
    service = TransactionService(session)

    # Try to create unbalanced multi-split transaction
    postings = [
        (sample_accounts["checking"].id, Decimal("100.00"), None),
        (sample_accounts["groceries"].id, Decimal("-50.00"), None),
        # Missing -50.00, so total != 0
    ]

    with pytest.raises(ValueError, match="does not balance"):
        service.create_multi_split_transaction(
            transaction_date=date.today(),
            description="Unbalanced",
            postings=postings,
        )


def test_account_balance_calculation(session, sample_accounts):
    """Test that account balances are calculated correctly."""
    service = TransactionService(session)
    account_service = AccountService(session)

    # Create multiple transactions
    service.create_simple_transaction(
        transaction_date=date.today(),
        description="Transaction 1",
        from_account_id=sample_accounts["checking"].id,
        to_account_id=sample_accounts["groceries"].id,
        amount=Decimal("50.00"),
    )

    service.create_simple_transaction(
        transaction_date=date.today(),
        description="Transaction 2",
        from_account_id=sample_accounts["checking"].id,
        to_account_id=sample_accounts["groceries"].id,
        amount=Decimal("30.00"),
    )

    session.commit()

    # Check balances
    checking_balance = account_service.get_account_balance(sample_accounts["checking"].id)
    groceries_balance = account_service.get_account_balance(sample_accounts["groceries"].id)

    # Checking (asset) is credited (negative) when money leaves
    assert checking_balance == Decimal("-80.00")
    # Groceries (expense) is debited (positive) when expense increases
    assert groceries_balance == Decimal("80.00")


def test_complex_multi_split_balances(session, sample_accounts):
    """Test balance calculation with complex multi-split transactions."""
    service = TransactionService(session)

    # Paycheck with multiple deductions
    postings = [
        (sample_accounts["checking"].id, Decimal("3000.00"), "Net pay"),
        (sample_accounts["salary"].id, Decimal("-5000.00"), "Gross salary"),
        (sample_accounts["groceries"].id, Decimal("750.00"), "Federal tax"),  # Using as tax placeholder
        (sample_accounts["restaurants"].id, Decimal("200.00"), "State tax"),  # Using as tax placeholder
        (sample_accounts["savings"].id, Decimal("-500.00"), "401k"),
        (sample_accounts["credit_card"].id, Decimal("1550.00"), "Total deductions"),
    ]

    # Verify balance
    total = sum(amount for _, amount, _ in postings)
    assert total == 0, "Test data must balance"

    service.create_multi_split_transaction(
        transaction_date=date.today(),
        description="Paycheck with deductions",
        postings=postings,
        payee="Employer",
    )

    session.commit()

    # Verify account balances
    account_service = AccountService(session)
    checking_balance = account_service.get_account_balance(sample_accounts["checking"].id)

    assert checking_balance == Decimal("3000.00")


def test_zero_sum_invariant(session, sample_accounts):
    """Test that all postings in database always sum to zero."""
    service = TransactionService(session)

    # Create several transactions
    service.create_simple_transaction(
        transaction_date=date.today(),
        description="Transaction 1",
        from_account_id=sample_accounts["checking"].id,
        to_account_id=sample_accounts["groceries"].id,
        amount=Decimal("100.00"),
    )

    service.create_simple_transaction(
        transaction_date=date.today(),
        description="Transaction 2",
        from_account_id=sample_accounts["salary"].id,
        to_account_id=sample_accounts["checking"].id,
        amount=Decimal("500.00"),
    )

    service.create_simple_transaction(
        transaction_date=date.today(),
        description="Transaction 3",
        from_account_id=sample_accounts["checking"].id,
        to_account_id=sample_accounts["restaurants"].id,
        amount=Decimal("75.00"),
    )

    session.commit()

    # Sum of all postings should be zero
    posting_repo = PostingRepository(session)
    all_postings = posting_repo.get_all()
    total = sum(p.amount for p in all_postings)

    assert total == 0, "Double-entry invariant violated: sum of all postings must be zero"
