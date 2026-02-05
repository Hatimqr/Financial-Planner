"""Initialize database with sample account structure."""

from pathlib import Path

from ledger.db.connection import get_db_manager
from ledger.db.models import Base
from ledger.services.account_service import AccountService


def initialize_database():
    """Initialize database and create sample account hierarchy."""
    # Ensure data directory exists
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    # Get database manager
    db_manager = get_db_manager()

    # Create all tables
    Base.metadata.create_all(db_manager.engine)

    print("✓ Database tables created")

    # Create sample accounts
    with db_manager.get_session() as session:
        service = AccountService(session)

        # Check if accounts already exist
        existing_accounts = service.get_account_tree()
        if existing_accounts:
            print("⚠ Accounts already exist. Skipping account creation.")
            return

        # Assets
        service.create_account("Assets", "asset", is_placeholder=True)
        service.create_account("Assets:Bank", "asset", is_placeholder=True)
        service.create_account("Assets:Bank:Checking", "asset")
        service.create_account("Assets:Bank:Savings", "asset")
        service.create_account("Assets:Cash", "asset")

        # Liabilities
        service.create_account("Liabilities", "liability", is_placeholder=True)
        service.create_account("Liabilities:CreditCard", "liability")

        # Income
        service.create_account("Income", "income", is_placeholder=True)
        service.create_account("Income:Salary", "income")
        service.create_account("Income:Interest", "income")

        # Expenses
        service.create_account("Expenses", "expense", is_placeholder=True)
        service.create_account("Expenses:Food", "expense", is_placeholder=True)
        service.create_account("Expenses:Food:Groceries", "expense")
        service.create_account("Expenses:Food:Restaurants", "expense")
        service.create_account("Expenses:Housing", "expense", is_placeholder=True)
        service.create_account("Expenses:Housing:Rent", "expense")
        service.create_account("Expenses:Housing:Utilities", "expense")
        service.create_account("Expenses:Transport", "expense")
        service.create_account("Expenses:Entertainment", "expense")

        # Equity
        service.create_account("Equity", "equity", is_placeholder=True)
        service.create_account("Equity:OpeningBalance", "equity")

    print("✓ Sample accounts created")
    print("\nDatabase initialized successfully!")
    print("\nAccount structure:")
    print("  Assets")
    print("    ├── Bank")
    print("    │   ├── Checking")
    print("    │   └── Savings")
    print("    └── Cash")
    print("  Liabilities")
    print("    └── CreditCard")
    print("  Income")
    print("    ├── Salary")
    print("    └── Interest")
    print("  Expenses")
    print("    ├── Food")
    print("    │   ├── Groceries")
    print("    │   └── Restaurants")
    print("    ├── Housing")
    print("    │   ├── Rent")
    print("    │   └── Utilities")
    print("    ├── Transport")
    print("    └── Entertainment")
    print("  Equity")
    print("    └── OpeningBalance")


if __name__ == "__main__":
    initialize_database()
