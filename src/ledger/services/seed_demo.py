"""Seed demo database with realistic UAE/AED personal finance data."""

from datetime import date, timedelta
from decimal import Decimal

from ledger.db.connection import DatabaseManager
from ledger.db.models import Base
from ledger.services.account_service import AccountService
from ledger.services.budget_service import BudgetService
from ledger.services.transaction_service import TransactionService


def seed_demo(db_manager: DatabaseManager):
    """Create a realistic UAE-based personal finance scenario in AED.

    Args:
        db_manager: Database manager pointing to the demo database.
    """
    # Create tables
    Base.metadata.create_all(db_manager.engine)

    with db_manager.get_session() as session:
        account_service = AccountService(session)
        txn_service = TransactionService(session)
        budget_service = BudgetService(session)

        # ── Accounts ──────────────────────────────────────────────
        # Assets
        account_service.create_account("Assets", "asset", currency="AED", is_placeholder=True)
        account_service.create_account("Assets:Bank", "asset", currency="AED", is_placeholder=True)
        account_service.create_account("Assets:Bank:ENBD", "asset", currency="AED")
        account_service.create_account("Assets:Bank:Savings", "asset", currency="AED")
        account_service.create_account("Assets:Cash", "asset", currency="AED")

        # Liabilities
        account_service.create_account("Liabilities", "liability", currency="AED", is_placeholder=True)
        account_service.create_account("Liabilities:CreditCard", "liability", currency="AED")

        # Income
        account_service.create_account("Income", "income", currency="AED", is_placeholder=True)
        account_service.create_account("Income:Salary", "income", currency="AED")
        account_service.create_account("Income:Freelance", "income", currency="AED")
        account_service.create_account("Income:Interest", "income", currency="AED")

        # Expenses
        account_service.create_account("Expenses", "expense", currency="AED", is_placeholder=True)
        account_service.create_account("Expenses:Food", "expense", currency="AED", is_placeholder=True)
        account_service.create_account("Expenses:Food:Groceries", "expense", currency="AED")
        account_service.create_account("Expenses:Food:Restaurants", "expense", currency="AED")
        account_service.create_account("Expenses:Food:Coffee", "expense", currency="AED")
        account_service.create_account("Expenses:Housing", "expense", currency="AED", is_placeholder=True)
        account_service.create_account("Expenses:Housing:Rent", "expense", currency="AED")
        account_service.create_account("Expenses:Housing:DEWA", "expense", currency="AED")
        account_service.create_account("Expenses:Housing:Internet", "expense", currency="AED")
        account_service.create_account("Expenses:Transport", "expense", currency="AED", is_placeholder=True)
        account_service.create_account("Expenses:Transport:Fuel", "expense", currency="AED")
        account_service.create_account("Expenses:Transport:Salik", "expense", currency="AED")
        account_service.create_account("Expenses:Transport:Parking", "expense", currency="AED")
        account_service.create_account("Expenses:Shopping", "expense", currency="AED")
        account_service.create_account("Expenses:Entertainment", "expense", currency="AED")
        account_service.create_account("Expenses:Health", "expense", currency="AED")
        account_service.create_account("Expenses:Subscriptions", "expense", currency="AED")

        # Equity
        account_service.create_account("Equity", "equity", currency="AED", is_placeholder=True)
        account_service.create_account("Equity:OpeningBalance", "equity", currency="AED")

        # Build account name -> id map
        accs = {a.name: a.id for a in account_service.get_account_tree()}

        # Helper aliases
        enbd = accs["Assets:Bank:ENBD"]
        savings = accs["Assets:Bank:Savings"]
        cc = accs["Liabilities:CreditCard"]
        salary = accs["Income:Salary"]
        freelance = accs["Income:Freelance"]
        interest = accs["Income:Interest"]
        groceries = accs["Expenses:Food:Groceries"]
        restaurants = accs["Expenses:Food:Restaurants"]
        coffee = accs["Expenses:Food:Coffee"]
        rent = accs["Expenses:Housing:Rent"]
        dewa = accs["Expenses:Housing:DEWA"]
        internet = accs["Expenses:Housing:Internet"]
        fuel = accs["Expenses:Transport:Fuel"]
        salik = accs["Expenses:Transport:Salik"]
        parking = accs["Expenses:Transport:Parking"]
        shopping = accs["Expenses:Shopping"]
        entertainment = accs["Expenses:Entertainment"]
        health = accs["Expenses:Health"]
        subs = accs["Expenses:Subscriptions"]
        opening = accs["Equity:OpeningBalance"]

        today = date.today()
        d0 = today - timedelta(days=90)  # ~3 months ago

        def d(offset):
            return d0 + timedelta(days=offset)

        # ── Transactions ──────────────────────────────────────────
        # (date, description, payee, from_id, to_id, amount)
        transactions = [
            # Opening balance
            (d(0), "Opening Balance", None, opening, enbd, Decimal("25000.00")),

            # ── Month 1 ─────────────────────────────────────────
            (d(1), "Salary January", "Employer", salary, enbd, Decimal("18000.00")),
            (d(2), "Rent January", "Landlord", enbd, rent, Decimal("5500.00")),
            (d(3), "DEWA January", "DEWA", enbd, dewa, Decimal("380.00")),
            (d(4), "du Internet", "du", enbd, internet, Decimal("399.00")),
            (d(5), "Carrefour Groceries", "Carrefour", enbd, groceries, Decimal("320.50")),
            (d(7), "Salik Toll", "Salik", enbd, salik, Decimal("24.00")),
            (d(8), "Morning Coffee", "Tim Hortons", enbd, coffee, Decimal("22.00")),
            (d(9), "Lunch at Nando's", "Nando's", enbd, restaurants, Decimal("95.00")),
            (d(10), "ADNOC Fuel", "ADNOC", enbd, fuel, Decimal("180.00")),
            (d(11), "Salik Toll", "Salik", enbd, salik, Decimal("12.00")),
            (d(12), "Lulu Groceries", "Lulu Hypermarket", enbd, groceries, Decimal("245.75")),
            (d(14), "Parking Mall of Emirates", "Parking", enbd, parking, Decimal("20.00")),
            (d(14), "Shopping - Clothes", "Zara", enbd, shopping, Decimal("450.00")),
            (d(15), "Netflix Subscription", "Netflix", enbd, subs, Decimal("55.00")),
            (d(15), "Spotify Subscription", "Spotify", enbd, subs, Decimal("40.00")),
            (d(16), "Coffee", "Starbucks", enbd, coffee, Decimal("28.00")),
            (d(17), "Dinner Out", "PF Chang's", enbd, restaurants, Decimal("220.00")),
            (d(18), "Salik Toll", "Salik", enbd, salik, Decimal("12.00")),
            (d(19), "Spinneys Groceries", "Spinneys", enbd, groceries, Decimal("185.00")),
            (d(20), "Gym Membership", "Fitness First", enbd, health, Decimal("300.00")),
            (d(21), "Parking Downtown", "RTA Parking", enbd, parking, Decimal("10.00")),
            (d(22), "Savings Transfer", None, enbd, savings, Decimal("3000.00")),
            (d(23), "Credit Card Payment", None, enbd, cc, Decimal("2000.00")),
            (d(24), "Coffee", "Tim Hortons", enbd, coffee, Decimal("20.00")),
            (d(25), "ENOC Fuel", "ENOC", enbd, fuel, Decimal("165.00")),
            (d(26), "Salik Toll", "Salik", enbd, salik, Decimal("24.00")),
            (d(27), "Cinema Tickets", "VOX Cinemas", enbd, entertainment, Decimal("120.00")),
            (d(28), "Carrefour Groceries", "Carrefour", enbd, groceries, Decimal("275.00")),

            # ── Month 2 ─────────────────────────────────────────
            (d(31), "Salary February", "Employer", salary, enbd, Decimal("18000.00")),
            (d(32), "Rent February", "Landlord", enbd, rent, Decimal("5500.00")),
            (d(33), "DEWA February", "DEWA", enbd, dewa, Decimal("420.00")),
            (d(34), "du Internet", "du", enbd, internet, Decimal("399.00")),
            (d(35), "Lulu Groceries", "Lulu Hypermarket", enbd, groceries, Decimal("310.25")),
            (d(36), "Freelance Project", "Client", freelance, enbd, Decimal("3500.00")),
            (d(37), "Salik Toll", "Salik", enbd, salik, Decimal("12.00")),
            (d(38), "Morning Coffee", "Starbucks", enbd, coffee, Decimal("32.00")),
            (d(39), "Shawarma Lunch", "Operation Falafel", enbd, restaurants, Decimal("85.00")),
            (d(40), "ADNOC Fuel", "ADNOC", enbd, fuel, Decimal("190.00")),
            (d(41), "Salik Toll", "Salik", enbd, salik, Decimal("24.00")),
            (d(42), "Spinneys Groceries", "Spinneys", enbd, groceries, Decimal("198.50")),
            (d(43), "Parking JBR", "Parking", enbd, parking, Decimal("15.00")),
            (d(44), "Brunch", "La Petite Maison", enbd, restaurants, Decimal("250.00")),
            (d(45), "Shopping - Electronics", "Sharaf DG", enbd, shopping, Decimal("799.00")),
            (d(46), "Coffee", "Tim Hortons", enbd, coffee, Decimal("25.00")),
            (d(47), "Salik Toll", "Salik", enbd, salik, Decimal("12.00")),
            (d(48), "Dental Checkup", "Dr. Smile Clinic", enbd, health, Decimal("250.00")),
            (d(49), "Carrefour Groceries", "Carrefour", enbd, groceries, Decimal("350.00")),
            (d(50), "Bowling Night", "Dubai Bowling", enbd, entertainment, Decimal("80.00")),
            (d(51), "Parking Dubai Mall", "Emaar Parking", enbd, parking, Decimal("5.00")),
            (d(52), "Savings Transfer", None, enbd, savings, Decimal("3000.00")),
            (d(53), "ENOC Fuel", "ENOC", enbd, fuel, Decimal("175.00")),
            (d(54), "Salik Toll", "Salik", enbd, salik, Decimal("12.00")),

            # ── Month 3 (current) ───────────────────────────────
            (d(61), "Salary March", "Employer", salary, enbd, Decimal("18000.00")),
            (d(62), "Rent March", "Landlord", enbd, rent, Decimal("5500.00")),
            (d(63), "DEWA March", "DEWA", enbd, dewa, Decimal("350.00")),
            (d(64), "du Internet", "du", enbd, internet, Decimal("399.00")),
            (d(65), "Lulu Groceries", "Lulu Hypermarket", enbd, groceries, Decimal("280.00")),
            (d(66), "Coffee", "Starbucks", enbd, coffee, Decimal("35.00")),
            (d(67), "Salik Toll", "Salik", enbd, salik, Decimal("24.00")),
            (d(68), "ADNOC Fuel", "ADNOC", enbd, fuel, Decimal("200.00")),
            (d(69), "Dinner at Zuma", "Zuma", enbd, restaurants, Decimal("180.00")),
            (d(70), "Carrefour Groceries", "Carrefour", enbd, groceries, Decimal("155.00")),
            (d(71), "Coffee", "Tim Hortons", enbd, coffee, Decimal("22.00")),
            (d(72), "Salik Toll", "Salik", enbd, salik, Decimal("12.00")),
            (d(73), "Parking Marina Mall", "Parking", enbd, parking, Decimal("10.00")),
            (d(74), "Desert Safari", "Arabian Adventures", enbd, entertainment, Decimal("280.00")),
            (d(75), "Spinneys Groceries", "Spinneys", enbd, groceries, Decimal("220.00")),
            (d(76), "Shopping - Home", "IKEA", enbd, shopping, Decimal("380.00")),
            (d(77), "Netflix Subscription", "Netflix", enbd, subs, Decimal("55.00")),
            (d(77), "Spotify Subscription", "Spotify", enbd, subs, Decimal("40.00")),
            (d(78), "Pharmacy", "Aster Pharmacy", enbd, health, Decimal("150.00")),
            (d(79), "Savings Transfer", None, enbd, savings, Decimal("3000.00")),

            # Interest earned on savings
            (d(30), "Interest Earned", "ENBD", interest, savings, Decimal("45.00")),
        ]

        for txn_date, desc, payee, from_id, to_id, amount in transactions:
            txn_service.create_simple_transaction(
                transaction_date=txn_date,
                description=desc,
                from_account_id=from_id,
                to_account_id=to_id,
                amount=amount,
                payee=payee,
            )

        # ── Budgets ───────────────────────────────────────────────
        budget_data = [
            (groceries, Decimal("1500.00")),
            (restaurants, Decimal("800.00")),
            (coffee, Decimal("200.00")),
            (dewa, Decimal("500.00")),
            (fuel, Decimal("500.00")),
            (entertainment, Decimal("400.00")),
            (shopping, Decimal("1000.00")),
            (subs, Decimal("150.00")),
        ]

        for account_id, amount in budget_data:
            budget_service.create_budget(
                account_id=account_id,
                amount=amount,
                period="monthly",
            )

    print(f"Demo database seeded: {len(transactions)} transactions, {len(budget_data)} budgets")
