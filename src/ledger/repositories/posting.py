"""Posting repository for posting queries and balance calculations."""

from datetime import date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ledger.db.models import Entry, Posting
from ledger.repositories.base import BaseRepository


class PostingRepository(BaseRepository[Posting]):
    """Repository for Posting model."""

    def __init__(self, session: Session):
        """Initialize posting repository."""
        super().__init__(session, Posting)

    def get_balance_for_accounts_in_period(
        self, account_ids: List[int], start_date: date, end_date: date
    ) -> Decimal:
        """
        Calculate total balance for multiple accounts within a date range.

        Args:
            account_ids: List of account IDs to sum
            start_date: Period start date (inclusive)
            end_date: Period end date (inclusive)

        Returns:
            Total balance as Decimal
        """
        if not account_ids:
            return Decimal("0")
        result = (
            self.session.query(func.sum(Posting.amount))
            .join(Entry)
            .filter(
                Posting.account_id.in_(account_ids),
                Entry.date >= start_date,
                Entry.date <= end_date,
            )
            .scalar()
        )
        return Decimal(str(result)) if result else Decimal("0")

    def get_account_balance(self, account_id: int) -> Decimal:
        """
        Calculate current balance for an account.

        The balance is the sum of all postings for the account.
        - Positive amounts are debits
        - Negative amounts are credits

        Args:
            account_id: Account ID

        Returns:
            Account balance as Decimal
        """
        result = (
            self.session.query(func.sum(Posting.amount))
            .filter_by(account_id=account_id)
            .scalar()
        )
        return Decimal(str(result)) if result else Decimal("0")

    def validate_entry_balance(self, entry_id: int) -> bool:
        """
        Check if entry's postings sum to zero (balanced transaction).

        Args:
            entry_id: Entry ID

        Returns:
            True if balanced, False otherwise
        """
        total = (
            self.session.query(func.sum(Posting.amount))
            .filter_by(entry_id=entry_id)
            .scalar()
        )
        if total is None:
            return False
        return Decimal(str(total)) == Decimal("0")

    def get_by_entry(self, entry_id: int) -> List[Posting]:
        """
        Get all postings for an entry.

        Args:
            entry_id: Entry ID

        Returns:
            List of postings
        """
        return self.session.query(Posting).filter_by(entry_id=entry_id).all()

    def get_balance_before_date(self, account_id: int, before_date: date) -> Decimal:
        """
        Calculate balance for an account from all postings before a given date.

        Args:
            account_id: Account ID
            before_date: Date (exclusive upper bound)

        Returns:
            Balance as Decimal (positive = net debit, negative = net credit)
        """
        result = (
            self.session.query(func.sum(Posting.amount))
            .join(Entry)
            .filter(
                Posting.account_id == account_id,
                Entry.date < before_date,
            )
            .scalar()
        )
        return Decimal(str(result)) if result else Decimal("0")

    def get_by_account_in_period(
        self, account_id: int, start_date: date, end_date: date
    ) -> List[Posting]:
        """
        Get all postings for an account within a date range.

        Args:
            account_id: Account ID
            start_date: Period start date (inclusive)
            end_date: Period end date (inclusive)

        Returns:
            List of postings with entry eagerly loaded, ordered by date
        """
        return (
            self.session.query(Posting)
            .join(Entry)
            .filter(
                Posting.account_id == account_id,
                Entry.date >= start_date,
                Entry.date <= end_date,
            )
            .options(joinedload(Posting.entry))
            .order_by(Entry.date)
            .all()
        )

    def get_by_account(self, account_id: int, limit: Optional[int] = None) -> List[Posting]:
        """
        Get all postings for an account.

        Args:
            account_id: Account ID
            limit: Maximum number of results (optional)

        Returns:
            List of postings
        """
        query = self.session.query(Posting).filter_by(account_id=account_id)

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_daily_totals_for_accounts(
        self, account_ids: List[int], start_date: date, end_date: date
    ) -> List[tuple]:
        """
        Get daily totals for a set of accounts within a date range.

        Returns:
            List of (date, Decimal) tuples ordered by date
        """
        if not account_ids:
            return []
        rows = (
            self.session.query(Entry.date, func.sum(Posting.amount))
            .join(Entry)
            .filter(
                Posting.account_id.in_(account_ids),
                Entry.date >= start_date,
                Entry.date <= end_date,
            )
            .group_by(Entry.date)
            .order_by(Entry.date)
            .all()
        )
        return [(row[0], Decimal(str(row[1]))) for row in rows]

