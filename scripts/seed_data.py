"""Seed database with sample transactions."""

from datetime import date, timedelta
from decimal import Decimal

from ledger.db.connection import get_db_manager
from ledger.services.account_service import AccountService
from ledger.services.transaction_service import TransactionService


def seed_data():
    """Create realistic sample transactions."""
    db_manager = get_db_manager()

    with db_manager.get_session() as session:
        account_service = AccountService(session)
        transaction_service = TransactionService(session)

        # Get account IDs
        accounts = {
            acc.name: acc.id for acc in account_service.get_account_tree()
        }

        # Check if transactions already exist
        existing_transactions = transaction_service.get_recent_transactions(limit=1)
        if existing_transactions:
            print("⚠ Transactions already exist. Skipping transaction creation.")
            return

        today = date.today()

        # Opening balance (60 days ago)
        # Money flows FROM Equity:OpeningBalance TO Checking
        opening_date = today - timedelta(days=60)
        transaction_service.create_simple_transaction(
            transaction_date=opening_date,
            description="Opening Balance",
            from_account_id=accounts["Equity:OpeningBalance"],
            to_account_id=accounts["Assets:Bank:Checking"],
            amount=Decimal("5000.00"),
            memo="Initial account balance",
        )
        print("✓ Created opening balance transaction")

        # Sample transactions over the last 2 months
        transactions = [
            # Month 1
            (opening_date + timedelta(days=5), "Salary Deposit", "Acme Corp",
             accounts["Income:Salary"], accounts["Assets:Bank:Checking"], Decimal("3500.00")),
            (opening_date + timedelta(days=6), "Rent Payment", "Landlord LLC",
             accounts["Assets:Bank:Checking"], accounts["Expenses:Housing:Rent"], Decimal("1500.00")),
            (opening_date + timedelta(days=8), "Grocery Shopping", "Whole Foods",
             accounts["Assets:Bank:Checking"], accounts["Expenses:Food:Groceries"], Decimal("125.50")),
            (opening_date + timedelta(days=10), "Electric Bill", "Power Co",
             accounts["Assets:Bank:Checking"], accounts["Expenses:Housing:Utilities"], Decimal("85.00")),
            (opening_date + timedelta(days=12), "Dinner Out", "Italian Restaurant",
             accounts["Assets:Bank:Checking"], accounts["Expenses:Food:Restaurants"], Decimal("67.80")),
            (opening_date + timedelta(days=14), "Gas Station", "Shell",
             accounts["Assets:Bank:Checking"], accounts["Expenses:Transport"], Decimal("45.00")),
            (opening_date + timedelta(days=16), "Savings Transfer", None,
             accounts["Assets:Bank:Checking"], accounts["Assets:Bank:Savings"], Decimal("500.00")),
            (opening_date + timedelta(days=18), "Grocery Shopping", "Trader Joes",
             accounts["Assets:Bank:Checking"], accounts["Expenses:Food:Groceries"], Decimal("89.25")),
            (opening_date + timedelta(days=20), "Movie Tickets", "Cinema",
             accounts["Assets:Bank:Checking"], accounts["Expenses:Entertainment"], Decimal("32.00")),
            (opening_date + timedelta(days=22), "Grocery Shopping", "Whole Foods",
             accounts["Assets:Bank:Checking"], accounts["Expenses:Food:Groceries"], Decimal("142.30")),
            (opening_date + timedelta(days=25), "Water Bill", "Water District",
             accounts["Assets:Bank:Checking"], accounts["Expenses:Housing:Utilities"], Decimal("42.50")),
            (opening_date + timedelta(days=28), "Coffee Shop", "Starbucks",
             accounts["Assets:Bank:Checking"], accounts["Expenses:Food:Restaurants"], Decimal("15.75")),

            # Month 2
            (opening_date + timedelta(days=35), "Salary Deposit", "Acme Corp",
             accounts["Income:Salary"], accounts["Assets:Bank:Checking"], Decimal("3500.00")),
            (opening_date + timedelta(days=36), "Rent Payment", "Landlord LLC",
             accounts["Assets:Bank:Checking"], accounts["Expenses:Housing:Rent"], Decimal("1500.00")),
            (opening_date + timedelta(days=38), "Grocery Shopping", "Safeway",
             accounts["Assets:Bank:Checking"], accounts["Expenses:Food:Groceries"], Decimal("156.90")),
            (opening_date + timedelta(days=40), "Gas Station", "Chevron",
             accounts["Assets:Bank:Checking"], accounts["Expenses:Transport"], Decimal("52.00")),
            (opening_date + timedelta(days=42), "Electric Bill", "Power Co",
             accounts["Assets:Bank:Checking"], accounts["Expenses:Housing:Utilities"], Decimal("92.00")),
            (opening_date + timedelta(days=44), "Dinner Out", "Sushi Restaurant",
             accounts["Assets:Bank:Checking"], accounts["Expenses:Food:Restaurants"], Decimal("78.50")),
            (opening_date + timedelta(days=46), "Grocery Shopping", "Whole Foods",
             accounts["Assets:Bank:Checking"], accounts["Expenses:Food:Groceries"], Decimal("112.40")),
            (opening_date + timedelta(days=48), "Savings Transfer", None,
             accounts["Assets:Bank:Checking"], accounts["Assets:Bank:Savings"], Decimal("600.00")),
            (opening_date + timedelta(days=50), "Concert Tickets", "Ticketmaster",
             accounts["Assets:Bank:Checking"], accounts["Expenses:Entertainment"], Decimal("125.00")),
            (opening_date + timedelta(days=52), "Grocery Shopping", "Trader Joes",
             accounts["Assets:Bank:Checking"], accounts["Expenses:Food:Groceries"], Decimal("95.75")),
            (opening_date + timedelta(days=54), "Internet Bill", "ISP Co",
             accounts["Assets:Bank:Checking"], accounts["Expenses:Housing:Utilities"], Decimal("79.99")),
            (opening_date + timedelta(days=56), "Lunch Out", "Cafe",
             accounts["Assets:Bank:Checking"], accounts["Expenses:Food:Restaurants"], Decimal("24.50")),
            (opening_date + timedelta(days=58), "Gas Station", "Shell",
             accounts["Assets:Bank:Checking"], accounts["Expenses:Transport"], Decimal("48.00")),
        ]

        # Interest income
        interest_date = opening_date + timedelta(days=30)
        transaction_service.create_simple_transaction(
            transaction_date=interest_date,
            description="Interest Earned",
            from_account_id=accounts["Income:Interest"],
            to_account_id=accounts["Assets:Bank:Savings"],
            amount=Decimal("12.50"),
            memo="Monthly interest",
        )

        # Create all transactions
        for trans_date, desc, payee, from_id, to_id, amount in transactions:
            transaction_service.create_simple_transaction(
                transaction_date=trans_date,
                description=desc,
                from_account_id=from_id,
                to_account_id=to_id,
                amount=amount,
                payee=payee,
            )

    print(f"✓ Created {len(transactions) + 2} sample transactions")
    print("\nSample data seeded successfully!")
    print("\nTransactions cover:")
    print("  • Opening balance: $5,000")
    print("  • 2 salary deposits: $3,500 each")
    print("  • Rent payments, groceries, dining out")
    print("  • Utilities, transportation, entertainment")
    print("  • Savings transfers")
    print("  • Interest income")


if __name__ == "__main__":
    seed_data()
