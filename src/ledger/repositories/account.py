"""Account repository for account-specific queries."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from ledger.db.models import Account
from ledger.repositories.base import BaseRepository


class AccountRepository(BaseRepository[Account]):
    """Repository for Account model."""

    def __init__(self, session: Session):
        """Initialize account repository."""
        super().__init__(session, Account)

    def get_by_name(self, name: str) -> Optional[Account]:
        """
        Get account by name.

        Args:
            name: Full account name (e.g., "Assets:Bank:Checking")

        Returns:
            Account or None if not found
        """
        return self.session.query(Account).filter_by(name=name).first()

    def get_active_accounts(self) -> List[Account]:
        """
        Get all non-archived accounts.

        Returns:
            List of active accounts
        """
        return self.session.query(Account).filter(Account.archived_at.is_(None)).all()

    def get_by_type(self, account_type: str) -> List[Account]:
        """
        Get all accounts of a specific type.

        Args:
            account_type: Account type (asset, liability, equity, income, expense)

        Returns:
            List of accounts matching the type
        """
        return self.session.query(Account).filter_by(type=account_type).all()

    def archive(self, account: Account) -> Account:
        """
        Soft delete an account by setting archived_at timestamp.

        Args:
            account: Account to archive

        Returns:
            Archived account
        """
        account.archived_at = datetime.utcnow()
        self.session.flush()
        return account

    def get_children(self, parent_path: str) -> List[Account]:
        """
        Get all child accounts of a parent.

        Args:
            parent_path: Parent account path (e.g., "Assets:Bank")

        Returns:
            List of child accounts (e.g., "Assets:Bank:Checking", "Assets:Bank:Savings")
        """
        return (
            self.session.query(Account)
            .filter(Account.name.like(f"{parent_path}:%"))
            .all()
        )

    def get_parent_path(self, account_name: str) -> Optional[str]:
        """
        Get parent account path from a child account name.

        Args:
            account_name: Full account name (e.g., "Assets:Bank:Checking")

        Returns:
            Parent path (e.g., "Assets:Bank") or None if top-level account
        """
        parts = account_name.split(":")
        if len(parts) <= 1:
            return None
        return ":".join(parts[:-1])

    def search_by_prefix(self, prefix: str, limit: int = 10) -> List[Account]:
        """
        Find accounts starting with prefix for autocomplete.

        Args:
            prefix: Account name prefix to search for
            limit: Maximum number of results to return

        Returns:
            List of matching accounts
        """
        return (
            self.session.query(Account)
            .filter(Account.name.like(f"{prefix}%"))
            .filter(Account.archived_at.is_(None))
            .order_by(Account.name)
            .limit(limit)
            .all()
        )

    def get_leaf_accounts(self, account_type: Optional[str] = None) -> List[Account]:
        """
        Get accounts that can have transactions (non-placeholders).

        Args:
            account_type: Optional filter by account type

        Returns:
            List of leaf (non-placeholder) accounts
        """
        query = (
            self.session.query(Account)
            .filter(Account.is_placeholder.is_(False))
            .filter(Account.archived_at.is_(None))
        )

        if account_type:
            query = query.filter(Account.type == account_type)

        return query.order_by(Account.name).all()

    def get_direct_children(self, parent_path: str) -> List[Account]:
        """
        Get only direct children, not all descendants.

        Args:
            parent_path: Parent account path (e.g., "Assets:Bank")

        Returns:
            List of direct child accounts only
        """
        parent_depth = parent_path.count(":")
        all_children = self.get_children(parent_path)
        return [acc for acc in all_children if acc.name.count(":") == parent_depth + 1]

    def get_by_depth(self, depth: int) -> List[Account]:
        """
        Get accounts at a specific depth in the hierarchy.

        Args:
            depth: Depth level (0 for top-level accounts like "Assets", "Expenses")

        Returns:
            List of accounts at the specified depth
        """
        all_accounts = self.get_active_accounts()
        return [acc for acc in all_accounts if acc.name.count(":") == depth]

    def get_root_accounts(self) -> List[Account]:
        """
        Get top-level accounts (Assets, Liabilities, Equity, Income, Expenses).

        Returns:
            List of root accounts
        """
        return self.get_by_depth(0)
