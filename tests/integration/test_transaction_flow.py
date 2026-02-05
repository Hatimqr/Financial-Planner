"""End-to-end transaction flow tests."""

from datetime import date
from decimal import Decimal

from ledger.services.account_service import AccountService
from ledger.services.transaction_service import TransactionService


def test_complete_transaction_flow(session):
    """Test complete flow from account creation to transaction."""
    account_service = AccountService(session)
    transaction_service = TransactionService(session)

    # Create accounts
    checking = account_service.create_account("Assets:Bank:Checking", "asset")
    groceries = account_service.create_account("Expenses:Food:Groceries", "expense")

    # Parents should be auto-created
    assert account_service.get_account_by_name("Assets") is not None
    assert account_service.get_account_by_name("Assets:Bank") is not None
    assert account_service.get_account_by_name("Expenses") is not None
    assert account_service.get_account_by_name("Expenses:Food") is not None

    # Create transaction
    entry = transaction_service.create_simple_transaction(
        transaction_date=date.today(),
        description="Grocery shopping",
        from_account_id=checking.id,
        to_account_id=groceries.id,
        amount=Decimal("125.50"),
        payee="Whole Foods",
    )

    session.commit()

    # Verify transaction
    assert entry.id is not None
    assert entry.description == "Grocery shopping"
    assert len(entry.postings) == 2

    # Verify balances
    checking_balance = account_service.get_account_balance(checking.id)
    groceries_balance = account_service.get_account_balance(groceries.id)

    # Checking (asset) is credited when money leaves
    assert checking_balance == Decimal("-125.50")
    # Groceries (expense) is debited when expense increases
    assert groceries_balance == Decimal("125.50")


def test_multiple_transactions_balance_correctly(session, sample_accounts):
    """Test that multiple transactions maintain correct balances."""
    account_service = AccountService(session)
    transaction_service = TransactionService(session)

    # Opening balance (FROM equity TO checking)
    transaction_service.create_simple_transaction(
        transaction_date=date.today(),
        description="Opening balance",
        from_account_id=sample_accounts["opening"].id,
        to_account_id=sample_accounts["checking"].id,
        amount=Decimal("5000.00"),
    )

    # Salary deposit
    transaction_service.create_simple_transaction(
        transaction_date=date.today(),
        description="Salary",
        from_account_id=sample_accounts["salary"].id,
        to_account_id=sample_accounts["checking"].id,
        amount=Decimal("3500.00"),
    )

    # Rent payment
    transaction_service.create_simple_transaction(
        transaction_date=date.today(),
        description="Rent",
        from_account_id=sample_accounts["checking"].id,
        to_account_id=sample_accounts["groceries"].id,  # Using as placeholder
        amount=Decimal("1500.00"),
    )

    # Groceries
    transaction_service.create_simple_transaction(
        transaction_date=date.today(),
        description="Groceries",
        from_account_id=sample_accounts["checking"].id,
        to_account_id=sample_accounts["groceries"].id,
        amount=Decimal("125.50"),
    )

    session.commit()

    # Verify final checking balance
    # 1. Opening: FROM Equity(-5000) TO Checking(+5000)
    # 2. Salary: FROM Income(-3500) TO Checking(+3500)
    # 3. Rent: FROM Checking(-1500) TO Expense(+1500)
    # 4. Groceries: FROM Checking(-125.50) TO Expense(+125.50)
    # Checking total: +5000 +3500 -1500 -125.50 = +6874.50
    checking_balance = account_service.get_account_balance(sample_accounts["checking"].id)
    assert checking_balance == Decimal("6874.50")


def test_account_hierarchy_with_transactions(session):
    """Test that account hierarchy works correctly with transactions."""
    account_service = AccountService(session)
    transaction_service = TransactionService(session)

    # Create hierarchical accounts
    account_service.create_account("Assets:Bank:Chase:Checking", "asset")
    account_service.create_account("Expenses:Food:Restaurants", "expense")

    # Get leaf accounts
    checking = account_service.get_account_by_name("Assets:Bank:Chase:Checking")
    restaurants = account_service.get_account_by_name("Expenses:Food:Restaurants")

    # Create transaction
    transaction_service.create_simple_transaction(
        transaction_date=date.today(),
        description="Dinner",
        from_account_id=checking.id,
        to_account_id=restaurants.id,
        amount=Decimal("75.00"),
    )

    session.commit()

    # Verify balances
    # FROM checking(-75) TO restaurants(+75)
    assert account_service.get_account_balance(checking.id) == Decimal("-75.00")
    assert account_service.get_account_balance(restaurants.id) == Decimal("75.00")

    # Verify parent accounts exist
    assert account_service.get_account_by_name("Assets:Bank:Chase") is not None
    assert account_service.get_account_by_name("Expenses:Food") is not None
