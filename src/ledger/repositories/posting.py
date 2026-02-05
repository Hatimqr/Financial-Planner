"""Posting repository for posting queries and balance calculations."""

from decimal import Decimal
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ledger.db.models import Posting
from ledger.repositories.base import BaseRepository


class PostingRepository(BaseRepository[Posting]):
    """Repository for Posting model."""

    def __init__(self, session: Session):
        """Initialize posting repository."""
        super().__init__(session, Posting)

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
        return Decimal(str(total)) == Decimal("0") if total else True

    def get_by_entry(self, entry_id: int) -> List[Posting]:
        """
        Get all postings for an entry.

        Args:
            entry_id: Entry ID

        Returns:
            List of postings
        """
        return self.session.query(Posting).filter_by(entry_id=entry_id).all()

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
