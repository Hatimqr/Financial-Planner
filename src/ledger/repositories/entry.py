"""Entry repository for transaction entry queries."""

from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from ledger.db.models import Entry, Posting
from ledger.repositories.base import BaseRepository


class EntryRepository(BaseRepository[Entry]):
    """Repository for Entry model."""

    def __init__(self, session: Session):
        """Initialize entry repository."""
        super().__init__(session, Entry)

    def get_with_postings(self, entry_id: int) -> Optional[Entry]:
        """
        Get entry with all postings eagerly loaded.

        Args:
            entry_id: Entry ID

        Returns:
            Entry with postings or None if not found
        """
        return (
            self.session.query(Entry)
            .options(joinedload(Entry.postings).joinedload(Posting.account))
            .filter_by(id=entry_id)
            .first()
        )

    def get_all_with_postings(self) -> List[Entry]:
        """
        Get all entries with postings eagerly loaded.

        Returns:
            List of all entries with postings and accounts loaded
        """
        return (
            self.session.query(Entry)
            .options(joinedload(Entry.postings).joinedload(Posting.account))
            .order_by(Entry.date.desc())
            .all()
        )

    def get_by_date_range(self, start_date: date, end_date: date) -> List[Entry]:
        """
        Get all entries within a date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of entries ordered by date descending
        """
        return (
            self.session.query(Entry)
            .filter(Entry.date >= start_date, Entry.date <= end_date)
            .order_by(Entry.date.desc())
            .all()
        )

    def get_by_account(self, account_id: int, limit: Optional[int] = None) -> List[Entry]:
        """
        Get all entries affecting a specific account.

        Args:
            account_id: Account ID
            limit: Maximum number of results (optional)

        Returns:
            List of entries ordered by date descending
        """
        query = (
            self.session.query(Entry)
            .join(Posting)
            .filter(Posting.account_id == account_id)
            .distinct()
            .order_by(Entry.date.desc())
        )

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_recent(self, limit: int = 10) -> List[Entry]:
        """
        Get most recent entries.

        Args:
            limit: Number of entries to return

        Returns:
            List of entries ordered by date descending
        """
        return (
            self.session.query(Entry)
            .order_by(Entry.date.desc())
            .limit(limit)
            .all()
        )
