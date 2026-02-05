"""Account service for account management business logic."""

from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from ledger.db.models import Account
from ledger.repositories.account import AccountRepository
from ledger.repositories.posting import PostingRepository


class AccountService:
    """Service for account management operations."""

    VALID_ACCOUNT_TYPES = ["asset", "liability", "equity", "income", "expense"]

    def __init__(self, session: Session):
        """
        Initialize account service.

        Args:
            session: SQLAlchemy session
        """
        self.session = session
        self.account_repo = AccountRepository(session)
        self.posting_repo = PostingRepository(session)

    def create_account(
        self,
        name: str,
        account_type: str,
        currency: str = "USD",
        is_placeholder: bool = False,
        notes: Optional[str] = None,
    ) -> Account:
        """
        Create a new account with validation.

        Automatically creates parent accounts as placeholders if they don't exist.

        Args:
            name: Full account name (e.g., "Assets:Bank:Chase:Checking")
            account_type: Account type (asset, liability, equity, income, expense)
            currency: Currency code (default: USD)
            is_placeholder: Whether this is a placeholder parent account
            notes: Optional notes

        Returns:
            Created account

        Raises:
            ValueError: If validation fails
        """
        # Validate account type
        account_type_lower = account_type.lower()
        if account_type_lower not in self.VALID_ACCOUNT_TYPES:
            raise ValueError(
                f"Invalid account type '{account_type}'. "
                f"Must be one of: {', '.join(self.VALID_ACCOUNT_TYPES)}"
            )

        # Check for duplicate names
        existing = self.account_repo.get_by_name(name)
        if existing:
            raise ValueError(f"Account '{name}' already exists")

        # Validate hierarchy (parent must have same type)
        if ":" in name:
            parent_path = self.account_repo.get_parent_path(name)
            if parent_path:
                parent = self.account_repo.get_by_name(parent_path)
                if parent:
                    # Parent exists - validate type matches
                    if parent.type != account_type_lower:
                        raise ValueError(
                            f"Account type '{account_type_lower}' doesn't match "
                            f"parent account type '{parent.type}' for '{parent_path}'"
                        )
                else:
                    # Parent doesn't exist - recursively create as placeholder
                    self.create_account(
                        name=parent_path,
                        account_type=account_type_lower,
                        currency=currency,
                        is_placeholder=True,
                        notes="Auto-created parent account",
                    )

        # Create account
        return self.account_repo.create(
            name=name,
            type=account_type_lower,
            currency=currency,
            is_placeholder=is_placeholder,
            notes=notes,
        )

    def get_account_by_id(self, account_id: int) -> Optional[Account]:
        """
        Get account by ID.

        Args:
            account_id: Account ID

        Returns:
            Account or None if not found
        """
        return self.account_repo.get_by_id(account_id)

    def get_account_by_name(self, name: str) -> Optional[Account]:
        """
        Get account by name.

        Args:
            name: Full account name

        Returns:
            Account or None if not found
        """
        return self.account_repo.get_by_name(name)

    def get_account_tree(self) -> List[Account]:
        """
        Get all active accounts organized hierarchically.

        Returns:
            List of accounts sorted by name for hierarchical display
        """
        accounts = self.account_repo.get_active_accounts()
        return sorted(accounts, key=lambda a: a.name)

    def get_accounts_by_type(self, account_type: str) -> List[Account]:
        """
        Get all accounts of a specific type.

        Args:
            account_type: Account type

        Returns:
            List of accounts

        Raises:
            ValueError: If account type is invalid
        """
        account_type_lower = account_type.lower()
        if account_type_lower not in self.VALID_ACCOUNT_TYPES:
            raise ValueError(f"Invalid account type: {account_type}")

        return self.account_repo.get_by_type(account_type_lower)

    def get_account_balance(self, account_id: int) -> Decimal:
        """
        Get current balance for an account.

        Args:
            account_id: Account ID

        Returns:
            Account balance as Decimal
        """
        return self.posting_repo.get_account_balance(account_id)

    def archive_account(self, account_id: int) -> Account:
        """
        Archive (soft delete) an account.

        Args:
            account_id: Account ID

        Returns:
            Archived account

        Raises:
            ValueError: If account not found
        """
        account = self.account_repo.get_by_id(account_id)
        if not account:
            raise ValueError(f"Account with ID {account_id} not found")

        return self.account_repo.archive(account)

    def update_account(
        self,
        account_id: int,
        name: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Account:
        """
        Update account properties.

        Args:
            account_id: Account ID
            name: New name (optional)
            notes: New notes (optional)

        Returns:
            Updated account

        Raises:
            ValueError: If account not found or validation fails
        """
        account = self.account_repo.get_by_id(account_id)
        if not account:
            raise ValueError(f"Account with ID {account_id} not found")

        updates = {}
        if name is not None:
            # Check if new name already exists
            existing = self.account_repo.get_by_name(name)
            if existing and existing.id != account_id:
                raise ValueError(f"Account '{name}' already exists")
            updates["name"] = name

        if notes is not None:
            updates["notes"] = notes

        if updates:
            return self.account_repo.update(account, **updates)

        return account

    def get_leaf_accounts(self, account_type: Optional[str] = None) -> List[Account]:
        """
        Get accounts that can have transactions (non-placeholders).

        Args:
            account_type: Optional filter by account type

        Returns:
            List of leaf accounts
        """
        return self.account_repo.get_leaf_accounts(account_type=account_type)

    def search_accounts(self, prefix: str, limit: int = 10) -> List[Account]:
        """
        Search accounts by name prefix for autocomplete.

        Args:
            prefix: Account name prefix
            limit: Maximum number of results

        Returns:
            List of matching accounts
        """
        return self.account_repo.search_by_prefix(prefix=prefix, limit=limit)

    def suggest_expense_account(
        self, description: str, payee: Optional[str] = None, limit: int = 5
    ) -> List[Account]:
        """
        Suggest expense accounts based on transaction description and payee.

        Uses simple keyword matching to categorize common transactions.

        Args:
            description: Transaction description
            payee: Optional payee name
            limit: Maximum number of suggestions

        Returns:
            List of suggested accounts (most likely first)
        """
        # Keyword mappings for common transaction types
        keyword_mappings = {
            # Food & Dining
            "grocery": "Expenses:Food:Groceries",
            "groceries": "Expenses:Food:Groceries",
            "supermarket": "Expenses:Food:Groceries",
            "whole foods": "Expenses:Food:Groceries",
            "trader joe": "Expenses:Food:Groceries",
            "safeway": "Expenses:Food:Groceries",
            "restaurant": "Expenses:Food:Restaurants",
            "dining": "Expenses:Food:Restaurants",
            "dinner": "Expenses:Food:Restaurants",
            "lunch": "Expenses:Food:Restaurants",
            "breakfast": "Expenses:Food:Restaurants",
            "cafe": "Expenses:Food:Restaurants",
            "coffee": "Expenses:Food:Restaurants",
            "starbucks": "Expenses:Food:Restaurants",
            # Housing
            "rent": "Expenses:Housing:Rent",
            "electric": "Expenses:Housing:Utilities",
            "electricity": "Expenses:Housing:Utilities",
            "power": "Expenses:Housing:Utilities",
            "water": "Expenses:Housing:Utilities",
            "gas bill": "Expenses:Housing:Utilities",
            "internet": "Expenses:Housing:Utilities",
            "utilities": "Expenses:Housing:Utilities",
            # Transportation
            "gas": "Expenses:Transport",
            "fuel": "Expenses:Transport",
            "shell": "Expenses:Transport",
            "chevron": "Expenses:Transport",
            "uber": "Expenses:Transport",
            "lyft": "Expenses:Transport",
            # Entertainment
            "movie": "Expenses:Entertainment",
            "cinema": "Expenses:Entertainment",
            "theater": "Expenses:Entertainment",
            "concert": "Expenses:Entertainment",
            "entertainment": "Expenses:Entertainment",
        }

        # Combine description and payee for matching
        search_text = description.lower()
        if payee:
            search_text += " " + payee.lower()

        # Find matching account
        for keyword, account_name in keyword_mappings.items():
            if keyword in search_text:
                account = self.account_repo.get_by_name(account_name)
                if account and account.is_leaf:
                    return [account]

        # No match found - return all leaf expense accounts
        return self.account_repo.get_leaf_accounts(account_type="expense")[:limit]

    def get_account_hierarchy_tree(self) -> List[Account]:
        """
        Get accounts organized as a hierarchical tree.

        Returns accounts sorted by name, which naturally creates tree ordering.

        Returns:
            List of all active accounts in tree order
        """
        return self.get_account_tree()

    def get_root_accounts(self) -> List[Account]:
        """
        Get top-level accounts (Assets, Liabilities, Equity, Income, Expenses).

        Returns:
            List of root accounts
        """
        return self.account_repo.get_root_accounts()
