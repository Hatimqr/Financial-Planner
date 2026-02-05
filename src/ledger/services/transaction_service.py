"""Transaction service for double-entry transaction management."""

from datetime import date
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from ledger.db.models import Entry
from ledger.repositories.account import AccountRepository
from ledger.repositories.entry import EntryRepository
from ledger.repositories.posting import PostingRepository


class TransactionService:
    """Service for transaction operations with double-entry validation."""

    def __init__(self, session: Session):
        """
        Initialize transaction service.

        Args:
            session: SQLAlchemy session
        """
        self.session = session
        self.entry_repo = EntryRepository(session)
        self.posting_repo = PostingRepository(session)
        self.account_repo = AccountRepository(session)

    def create_simple_transaction(
        self,
        transaction_date: date,
        description: str,
        from_account_id: int,
        to_account_id: int,
        amount: Decimal,
        payee: Optional[str] = None,
        memo: Optional[str] = None,
    ) -> Entry:
        """
        Create a simple two-account transaction.

        This is the most common transaction type: moving money from one account to another.

        Args:
            transaction_date: Transaction date
            description: Transaction description
            from_account_id: Source account ID (will be credited - money leaving)
            to_account_id: Destination account ID (will be debited - money arriving)
            amount: Positive amount to transfer
            payee: Optional payee name
            memo: Optional memo for postings

        Returns:
            Created entry

        Raises:
            ValueError: If validation fails
        """
        # Validate amount
        if amount <= 0:
            raise ValueError("Amount must be positive")

        # Validate accounts exist
        from_account = self.account_repo.get_by_id(from_account_id)
        to_account = self.account_repo.get_by_id(to_account_id)

        if not from_account:
            raise ValueError(f"Source account ID {from_account_id} not found")
        if not to_account:
            raise ValueError(f"Destination account ID {to_account_id} not found")

        # Validate accounts are not the same
        if from_account_id == to_account_id:
            raise ValueError("Source and destination accounts cannot be the same")

        # Create entry
        entry = self.entry_repo.create(
            date=transaction_date,
            description=description,
            payee=payee,
            status="cleared",
        )

        # Create postings (double-entry)
        # Credit (negative) the source account (money leaving)
        self.posting_repo.create(
            entry_id=entry.id, account_id=from_account_id, amount=-amount, memo=memo
        )

        # Debit (positive) the destination account (money arriving)
        self.posting_repo.create(
            entry_id=entry.id, account_id=to_account_id, amount=amount, memo=memo
        )

        # Flush to database
        self.session.flush()

        # Validate balance (should always be zero for this simple transaction)
        if not self.posting_repo.validate_entry_balance(entry.id):
            raise ValueError("Transaction does not balance (internal error)")

        return entry

    def create_multi_split_transaction(
        self,
        transaction_date: date,
        description: str,
        postings: List[Tuple[int, Decimal, Optional[str]]],
        payee: Optional[str] = None,
    ) -> Entry:
        """
        Create a transaction with multiple postings (splits).

        Useful for complex transactions like paychecks with multiple deductions.

        Args:
            transaction_date: Transaction date
            description: Transaction description
            postings: List of (account_id, amount, memo) tuples
            payee: Optional payee name

        Returns:
            Created entry

        Raises:
            ValueError: If validation fails
        """
        # Validate we have at least 2 postings
        if len(postings) < 2:
            raise ValueError("A transaction must have at least 2 postings")

        # Validate balance before creating
        total = sum(amount for _, amount, _ in postings)
        if total != 0:
            raise ValueError(
                f"Transaction does not balance. Sum of postings: {total} (should be 0)"
            )

        # Validate all accounts exist
        for account_id, _, _ in postings:
            if not self.account_repo.get_by_id(account_id):
                raise ValueError(f"Account ID {account_id} does not exist")

        # Create entry
        entry = self.entry_repo.create(
            date=transaction_date, description=description, payee=payee, status="cleared"
        )

        # Create all postings
        for account_id, amount, memo in postings:
            self.posting_repo.create(
                entry_id=entry.id, account_id=account_id, amount=amount, memo=memo
            )

        # Flush to trigger database validation
        self.session.flush()

        return entry

    def get_transaction_by_id(self, entry_id: int) -> Optional[Entry]:
        """
        Get transaction by ID with all postings loaded.

        Args:
            entry_id: Entry ID

        Returns:
            Entry with postings or None if not found
        """
        return self.entry_repo.get_with_postings(entry_id)

    def get_transactions_by_account(self, account_id: int, limit: Optional[int] = None) -> List[Entry]:
        """
        Get all transactions affecting a specific account.

        Args:
            account_id: Account ID
            limit: Maximum number of results (optional)

        Returns:
            List of entries
        """
        return self.entry_repo.get_by_account(account_id, limit=limit)

    def get_transactions_by_date_range(
        self, start_date: date, end_date: date
    ) -> List[Entry]:
        """
        Get all transactions within a date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of entries
        """
        return self.entry_repo.get_by_date_range(start_date, end_date)

    def get_recent_transactions(self, limit: int = 10) -> List[Entry]:
        """
        Get most recent transactions.

        Args:
            limit: Number of transactions to return

        Returns:
            List of entries
        """
        return self.entry_repo.get_recent(limit)

    def delete_transaction(self, entry_id: int) -> None:
        """
        Delete a transaction.

        Args:
            entry_id: Entry ID

        Raises:
            ValueError: If entry not found
        """
        entry = self.entry_repo.get_by_id(entry_id)
        if not entry:
            raise ValueError(f"Transaction with ID {entry_id} not found")

        self.entry_repo.delete(entry)
