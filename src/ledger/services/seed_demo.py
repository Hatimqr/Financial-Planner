"""Seed demo database with realistic UAE/AED personal finance data.

Generates 6 calendar months of data (Sep 2025 – Feb 2026) with:
- Multiple income streams (salary, freelance, dividends, interest)
- Deep expense hierarchies for drill-down testing
- Two bank accounts + savings + investment + two credit cards
- Budgets for all major expense categories
- Realistic seasonal variation (holidays, travel, etc.)
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import List, Tuple

from ledger.db.connection import DatabaseManager
from ledger.db.models import Base
from ledger.services.account_service import AccountService
from ledger.services.budget_service import BudgetService
from ledger.services.transaction_service import TransactionService


def seed_demo(db_manager: DatabaseManager):
    """Create a rich UAE-based personal finance scenario in AED."""
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
        account_service.create_account("Assets:Bank:ADCB", "asset", currency="AED")
        account_service.create_account("Assets:Bank:Savings", "asset", currency="AED")
        account_service.create_account("Assets:Investments", "asset", currency="AED", is_placeholder=True)
        account_service.create_account("Assets:Investments:Stocks", "asset", currency="AED")
        account_service.create_account("Assets:Investments:Crypto", "asset", currency="AED")
        account_service.create_account("Assets:Cash", "asset", currency="AED")

        # Liabilities
        account_service.create_account("Liabilities", "liability", currency="AED", is_placeholder=True)
        account_service.create_account("Liabilities:CreditCard", "liability", currency="AED", is_placeholder=True)
        account_service.create_account("Liabilities:CreditCard:Visa", "liability", currency="AED")
        account_service.create_account("Liabilities:CreditCard:Amex", "liability", currency="AED")
        account_service.create_account("Liabilities:CarLoan", "liability", currency="AED")

        # Income
        account_service.create_account("Income", "income", currency="AED", is_placeholder=True)
        account_service.create_account("Income:Salary", "income", currency="AED")
        account_service.create_account("Income:Freelance", "income", currency="AED", is_placeholder=True)
        account_service.create_account("Income:Freelance:WebDev", "income", currency="AED")
        account_service.create_account("Income:Freelance:Consulting", "income", currency="AED")
        account_service.create_account("Income:Dividends", "income", currency="AED")
        account_service.create_account("Income:Interest", "income", currency="AED")
        account_service.create_account("Income:Cashback", "income", currency="AED")

        # Expenses — deep hierarchy for drill-down
        account_service.create_account("Expenses", "expense", currency="AED", is_placeholder=True)

        account_service.create_account("Expenses:Food", "expense", currency="AED", is_placeholder=True)
        account_service.create_account("Expenses:Food:Groceries", "expense", currency="AED")
        account_service.create_account("Expenses:Food:Restaurants", "expense", currency="AED")
        account_service.create_account("Expenses:Food:Coffee", "expense", currency="AED")
        account_service.create_account("Expenses:Food:Delivery", "expense", currency="AED")

        account_service.create_account("Expenses:Housing", "expense", currency="AED", is_placeholder=True)
        account_service.create_account("Expenses:Housing:Rent", "expense", currency="AED")
        account_service.create_account("Expenses:Housing:DEWA", "expense", currency="AED")
        account_service.create_account("Expenses:Housing:Internet", "expense", currency="AED")
        account_service.create_account("Expenses:Housing:Maintenance", "expense", currency="AED")

        account_service.create_account("Expenses:Transport", "expense", currency="AED", is_placeholder=True)
        account_service.create_account("Expenses:Transport:Fuel", "expense", currency="AED")
        account_service.create_account("Expenses:Transport:Salik", "expense", currency="AED")
        account_service.create_account("Expenses:Transport:Parking", "expense", currency="AED")
        account_service.create_account("Expenses:Transport:CarLoan", "expense", currency="AED")
        account_service.create_account("Expenses:Transport:Insurance", "expense", currency="AED")

        account_service.create_account("Expenses:Shopping", "expense", currency="AED", is_placeholder=True)
        account_service.create_account("Expenses:Shopping:Clothes", "expense", currency="AED")
        account_service.create_account("Expenses:Shopping:Electronics", "expense", currency="AED")
        account_service.create_account("Expenses:Shopping:Home", "expense", currency="AED")

        account_service.create_account("Expenses:Entertainment", "expense", currency="AED", is_placeholder=True)
        account_service.create_account("Expenses:Entertainment:Cinema", "expense", currency="AED")
        account_service.create_account("Expenses:Entertainment:Games", "expense", currency="AED")
        account_service.create_account("Expenses:Entertainment:Events", "expense", currency="AED")

        account_service.create_account("Expenses:Health", "expense", currency="AED", is_placeholder=True)
        account_service.create_account("Expenses:Health:Gym", "expense", currency="AED")
        account_service.create_account("Expenses:Health:Medical", "expense", currency="AED")
        account_service.create_account("Expenses:Health:Pharmacy", "expense", currency="AED")

        account_service.create_account("Expenses:Subscriptions", "expense", currency="AED", is_placeholder=True)
        account_service.create_account("Expenses:Subscriptions:Streaming", "expense", currency="AED")
        account_service.create_account("Expenses:Subscriptions:Apps", "expense", currency="AED")
        account_service.create_account("Expenses:Subscriptions:Cloud", "expense", currency="AED")

        account_service.create_account("Expenses:Travel", "expense", currency="AED", is_placeholder=True)
        account_service.create_account("Expenses:Travel:Flights", "expense", currency="AED")
        account_service.create_account("Expenses:Travel:Hotels", "expense", currency="AED")
        account_service.create_account("Expenses:Travel:Activities", "expense", currency="AED")

        account_service.create_account("Expenses:Education", "expense", currency="AED")
        account_service.create_account("Expenses:Gifts", "expense", currency="AED")

        # Equity
        account_service.create_account("Equity", "equity", currency="AED", is_placeholder=True)
        account_service.create_account("Equity:OpeningBalance", "equity", currency="AED")

        # Build account name -> id map
        accs = {a.name: a.id for a in account_service.get_account_tree()}

        # Helper aliases
        enbd = accs["Assets:Bank:ENBD"]
        adcb = accs["Assets:Bank:ADCB"]
        savings = accs["Assets:Bank:Savings"]
        stocks = accs["Assets:Investments:Stocks"]
        crypto = accs["Assets:Investments:Crypto"]
        cash = accs["Assets:Cash"]

        visa = accs["Liabilities:CreditCard:Visa"]
        amex = accs["Liabilities:CreditCard:Amex"]
        car_loan = accs["Liabilities:CarLoan"]

        salary = accs["Income:Salary"]
        freelance_web = accs["Income:Freelance:WebDev"]
        freelance_consult = accs["Income:Freelance:Consulting"]
        dividends = accs["Income:Dividends"]
        interest = accs["Income:Interest"]
        cashback = accs["Income:Cashback"]

        groceries = accs["Expenses:Food:Groceries"]
        restaurants = accs["Expenses:Food:Restaurants"]
        coffee = accs["Expenses:Food:Coffee"]
        delivery = accs["Expenses:Food:Delivery"]

        rent = accs["Expenses:Housing:Rent"]
        dewa = accs["Expenses:Housing:DEWA"]
        internet_bill = accs["Expenses:Housing:Internet"]
        maintenance = accs["Expenses:Housing:Maintenance"]

        fuel = accs["Expenses:Transport:Fuel"]
        salik = accs["Expenses:Transport:Salik"]
        parking = accs["Expenses:Transport:Parking"]
        car_loan_exp = accs["Expenses:Transport:CarLoan"]
        car_insurance = accs["Expenses:Transport:Insurance"]

        clothes = accs["Expenses:Shopping:Clothes"]
        electronics = accs["Expenses:Shopping:Electronics"]
        home_shopping = accs["Expenses:Shopping:Home"]

        cinema = accs["Expenses:Entertainment:Cinema"]
        games = accs["Expenses:Entertainment:Games"]
        events = accs["Expenses:Entertainment:Events"]

        gym = accs["Expenses:Health:Gym"]
        medical = accs["Expenses:Health:Medical"]
        pharmacy = accs["Expenses:Health:Pharmacy"]

        streaming = accs["Expenses:Subscriptions:Streaming"]
        apps = accs["Expenses:Subscriptions:Apps"]
        cloud = accs["Expenses:Subscriptions:Cloud"]

        flights = accs["Expenses:Travel:Flights"]
        hotels = accs["Expenses:Travel:Hotels"]
        activities = accs["Expenses:Travel:Activities"]

        education = accs["Expenses:Education"]
        gifts = accs["Expenses:Gifts"]

        opening = accs["Equity:OpeningBalance"]

        # ── Transactions ──────────────────────────────────────────
        # 6 months: Sep 2025 – Feb 2026
        transactions: List[Tuple] = []

        def t(d, desc, payee, from_id, to_id, amount):
            """Shorthand to append a transaction."""
            transactions.append((d, desc, payee, from_id, to_id, Decimal(str(amount))))

        # ── Opening balances (Sep 1 2025) ─────────────────────────
        t(date(2025, 9, 1), "Opening Balance - ENBD", None, opening, enbd, 35000)
        t(date(2025, 9, 1), "Opening Balance - ADCB", None, opening, adcb, 12000)
        t(date(2025, 9, 1), "Opening Balance - Savings", None, opening, savings, 50000)
        t(date(2025, 9, 1), "Opening Balance - Stocks", None, opening, stocks, 25000)
        t(date(2025, 9, 1), "Opening Balance - Crypto", None, opening, crypto, 5000)
        t(date(2025, 9, 1), "Opening Balance - Cash", None, opening, cash, 2000)
        # Outstanding credit card balances (liabilities are credit-normal)
        t(date(2025, 9, 1), "Opening Balance - Visa", None, opening, visa, 3500)
        t(date(2025, 9, 1), "Opening Balance - Amex", None, opening, amex, 1200)
        t(date(2025, 9, 1), "Opening Balance - Car Loan", None, opening, car_loan, 45000)

        # ── Monthly recurring template ────────────────────────────
        def add_monthly_recurring(year, month):
            """Add recurring monthly expenses."""
            m1 = date(year, month, 1)
            # Salary on 28th (or last day if shorter month)
            import calendar
            last_day = calendar.monthrange(year, month)[1]
            salary_day = min(28, last_day)
            t(date(year, month, salary_day), f"Salary {m1.strftime('%B')}", "Employer", salary, enbd, 22000)

            # Rent on 1st
            t(m1, f"Rent {m1.strftime('%B')}", "Landlord", enbd, rent, 5500)

            # DEWA varies by season (summer = higher)
            dewa_amount = 650 if month in (6, 7, 8, 9) else 380 if month in (12, 1, 2) else 450
            t(date(year, month, 5), f"DEWA {m1.strftime('%B')}", "DEWA", enbd, dewa, dewa_amount)

            # Internet
            t(date(year, month, 10), "du Internet", "du", enbd, internet_bill, 399)

            # Car loan payment
            t(date(year, month, 15), "Car Loan Payment", "ENBD Auto", enbd, car_loan_exp, 1850)
            # Car loan liability reduction
            t(date(year, month, 15), "Car Loan Principal", None, car_loan, enbd, 1200)

            # Subscriptions
            t(date(year, month, 1), "Netflix", "Netflix", visa, streaming, 55)
            t(date(year, month, 1), "Spotify", "Spotify", visa, streaming, 40)
            t(date(year, month, 1), "YouTube Premium", "Google", visa, apps, 30)
            t(date(year, month, 5), "iCloud Storage", "Apple", visa, cloud, 15)
            t(date(year, month, 5), "GitHub Pro", "GitHub", visa, cloud, 20)

            # Gym
            t(date(year, month, 1), "Gym Membership", "Fitness First", enbd, gym, 300)

            # Savings transfer
            t(date(year, month, 28 if salary_day >= 28 else salary_day), "Savings Transfer", None, enbd, savings, 3500)

            # Interest earned on savings
            t(date(year, month, last_day), "Interest Earned", "ENBD", interest, savings, 65)

        # ── Month-specific transactions ───────────────────────────

        # === SEPTEMBER 2025 ===
        add_monthly_recurring(2025, 9)
        t(date(2025, 9, 2), "Carrefour Groceries", "Carrefour", enbd, groceries, 320)
        t(date(2025, 9, 5), "Lulu Groceries", "Lulu", enbd, groceries, 245)
        t(date(2025, 9, 9), "Spinneys Groceries", "Spinneys", enbd, groceries, 185)
        t(date(2025, 9, 13), "Carrefour Groceries", "Carrefour", enbd, groceries, 275)
        t(date(2025, 9, 18), "Lulu Groceries", "Lulu", enbd, groceries, 198)
        t(date(2025, 9, 22), "Spinneys Groceries", "Spinneys", enbd, groceries, 310)
        t(date(2025, 9, 27), "Carrefour Groceries", "Carrefour", enbd, groceries, 265)

        t(date(2025, 9, 3), "Morning Coffee", "Tim Hortons", enbd, coffee, 22)
        t(date(2025, 9, 7), "Coffee", "Starbucks", visa, coffee, 28)
        t(date(2025, 9, 11), "Coffee", "Tim Hortons", enbd, coffee, 20)
        t(date(2025, 9, 15), "Coffee", "Starbucks", visa, coffee, 32)
        t(date(2025, 9, 19), "Coffee", "Tim Hortons", enbd, coffee, 22)
        t(date(2025, 9, 24), "Coffee", "Caribou", enbd, coffee, 25)

        t(date(2025, 9, 4), "Lunch at Nando's", "Nando's", enbd, restaurants, 95)
        t(date(2025, 9, 10), "Dinner at PF Chang's", "PF Chang's", visa, restaurants, 220)
        t(date(2025, 9, 17), "Shawarma", "Operation Falafel", cash, restaurants, 45)
        t(date(2025, 9, 25), "Friday Brunch", "Atlantis", visa, restaurants, 350)

        t(date(2025, 9, 6), "Talabat Order", "Talabat", visa, delivery, 85)
        t(date(2025, 9, 14), "Deliveroo Order", "Deliveroo", visa, delivery, 65)
        t(date(2025, 9, 21), "Talabat Order", "Talabat", visa, delivery, 72)

        t(date(2025, 9, 3), "ADNOC Fuel", "ADNOC", enbd, fuel, 180)
        t(date(2025, 9, 12), "ENOC Fuel", "ENOC", enbd, fuel, 165)
        t(date(2025, 9, 21), "ADNOC Fuel", "ADNOC", enbd, fuel, 190)

        t(date(2025, 9, 4), "Salik Toll", "Salik", enbd, salik, 12)
        t(date(2025, 9, 8), "Salik Toll", "Salik", enbd, salik, 24)
        t(date(2025, 9, 15), "Salik Toll", "Salik", enbd, salik, 12)
        t(date(2025, 9, 22), "Salik Toll", "Salik", enbd, salik, 24)
        t(date(2025, 9, 29), "Salik Toll", "Salik", enbd, salik, 12)

        t(date(2025, 9, 7), "Parking MOE", "Parking", enbd, parking, 20)
        t(date(2025, 9, 14), "Parking Downtown", "RTA", enbd, parking, 10)

        t(date(2025, 9, 12), "Zara Shopping", "Zara", amex, clothes, 450)
        t(date(2025, 9, 20), "VOX Cinema", "VOX", visa, cinema, 120)
        t(date(2025, 9, 8), "Pharmacy", "Aster", enbd, pharmacy, 85)

        t(date(2025, 9, 15), "Freelance - Website", "Client A", freelance_web, adcb, 4500)
        t(date(2025, 9, 25), "Visa Payment", None, enbd, visa, 2500)
        t(date(2025, 9, 26), "Amex Payment", None, enbd, amex, 1000)

        # === OCTOBER 2025 ===
        add_monthly_recurring(2025, 10)
        t(date(2025, 10, 2), "Carrefour Groceries", "Carrefour", enbd, groceries, 340)
        t(date(2025, 10, 7), "Lulu Groceries", "Lulu", enbd, groceries, 280)
        t(date(2025, 10, 12), "Spinneys Groceries", "Spinneys", enbd, groceries, 195)
        t(date(2025, 10, 17), "Carrefour Groceries", "Carrefour", enbd, groceries, 310)
        t(date(2025, 10, 22), "Lulu Groceries", "Lulu", enbd, groceries, 225)
        t(date(2025, 10, 28), "Spinneys Groceries", "Spinneys", enbd, groceries, 290)

        t(date(2025, 10, 3), "Coffee", "Starbucks", visa, coffee, 28)
        t(date(2025, 10, 8), "Coffee", "Tim Hortons", enbd, coffee, 20)
        t(date(2025, 10, 13), "Coffee", "Caribou", enbd, coffee, 25)
        t(date(2025, 10, 18), "Coffee", "Starbucks", visa, coffee, 35)
        t(date(2025, 10, 23), "Coffee", "Tim Hortons", enbd, coffee, 22)

        t(date(2025, 10, 5), "Dinner at Zuma", "Zuma", amex, restaurants, 380)
        t(date(2025, 10, 11), "Lunch", "Shake Shack", enbd, restaurants, 85)
        t(date(2025, 10, 19), "Friday Brunch", "Four Seasons", visa, restaurants, 420)
        t(date(2025, 10, 26), "Dinner Out", "Nobu", amex, restaurants, 550)

        t(date(2025, 10, 4), "Talabat Order", "Talabat", visa, delivery, 78)
        t(date(2025, 10, 10), "Deliveroo Order", "Deliveroo", visa, delivery, 55)
        t(date(2025, 10, 16), "Talabat Order", "Talabat", visa, delivery, 90)
        t(date(2025, 10, 24), "Noon Food", "Noon", visa, delivery, 62)

        t(date(2025, 10, 3), "ADNOC Fuel", "ADNOC", enbd, fuel, 175)
        t(date(2025, 10, 14), "ENOC Fuel", "ENOC", enbd, fuel, 180)
        t(date(2025, 10, 25), "ADNOC Fuel", "ADNOC", enbd, fuel, 170)

        t(date(2025, 10, 2), "Salik Toll", "Salik", enbd, salik, 24)
        t(date(2025, 10, 9), "Salik Toll", "Salik", enbd, salik, 12)
        t(date(2025, 10, 16), "Salik Toll", "Salik", enbd, salik, 24)
        t(date(2025, 10, 23), "Salik Toll", "Salik", enbd, salik, 12)
        t(date(2025, 10, 30), "Salik Toll", "Salik", enbd, salik, 24)

        t(date(2025, 10, 6), "Parking JBR", "Parking", enbd, parking, 15)
        t(date(2025, 10, 18), "Parking Dubai Mall", "Emaar", enbd, parking, 5)

        t(date(2025, 10, 8), "H&M Shopping", "H&M", visa, clothes, 320)
        t(date(2025, 10, 15), "iPhone Case", "Apple Store", amex, electronics, 199)
        t(date(2025, 10, 20), "IKEA Home", "IKEA", enbd, home_shopping, 850)

        t(date(2025, 10, 12), "VOX Cinema", "VOX", visa, cinema, 95)
        t(date(2025, 10, 22), "Gaming Purchase", "PlayStation", visa, games, 250)

        t(date(2025, 10, 9), "Dental Checkup", "Dr. Smile", enbd, medical, 350)
        t(date(2025, 10, 20), "Pharmacy", "Aster", enbd, pharmacy, 120)

        t(date(2025, 10, 10), "Freelance - Consulting", "Client B", freelance_consult, adcb, 3000)
        t(date(2025, 10, 20), "Dividend - MSFT", "Broker", dividends, stocks, 850)
        t(date(2025, 10, 25), "Cashback Reward", "ENBD", cashback, enbd, 150)

        t(date(2025, 10, 25), "Visa Payment", None, enbd, visa, 3000)
        t(date(2025, 10, 26), "Amex Payment", None, enbd, amex, 1500)

        t(date(2025, 10, 15), "Online Course - Python", "Udemy", visa, education, 120)

        # === NOVEMBER 2025 ===
        add_monthly_recurring(2025, 11)
        t(date(2025, 11, 1), "Carrefour Groceries", "Carrefour", enbd, groceries, 290)
        t(date(2025, 11, 6), "Lulu Groceries", "Lulu", enbd, groceries, 310)
        t(date(2025, 11, 11), "Spinneys Groceries", "Spinneys", enbd, groceries, 220)
        t(date(2025, 11, 16), "Carrefour Groceries", "Carrefour", enbd, groceries, 345)
        t(date(2025, 11, 21), "Lulu Groceries", "Lulu", enbd, groceries, 255)
        t(date(2025, 11, 27), "Spinneys Groceries", "Spinneys", enbd, groceries, 280)

        t(date(2025, 11, 2), "Coffee", "Starbucks", visa, coffee, 30)
        t(date(2025, 11, 6), "Coffee", "Tim Hortons", enbd, coffee, 22)
        t(date(2025, 11, 10), "Coffee", "Caribou", enbd, coffee, 28)
        t(date(2025, 11, 14), "Coffee", "Starbucks", visa, coffee, 32)
        t(date(2025, 11, 18), "Coffee", "Tim Hortons", enbd, coffee, 20)
        t(date(2025, 11, 25), "Coffee", "Starbucks", visa, coffee, 35)

        t(date(2025, 11, 3), "Dinner", "Coya", amex, restaurants, 480)
        t(date(2025, 11, 8), "Lunch", "Five Guys", enbd, restaurants, 75)
        t(date(2025, 11, 15), "Friday Brunch", "Jumeirah", visa, restaurants, 380)
        t(date(2025, 11, 22), "Birthday Dinner", "Pierchic", amex, restaurants, 650)

        t(date(2025, 11, 5), "Talabat Order", "Talabat", visa, delivery, 82)
        t(date(2025, 11, 12), "Deliveroo Order", "Deliveroo", visa, delivery, 68)
        t(date(2025, 11, 20), "Talabat Order", "Talabat", visa, delivery, 95)

        t(date(2025, 11, 4), "ADNOC Fuel", "ADNOC", enbd, fuel, 185)
        t(date(2025, 11, 15), "ENOC Fuel", "ENOC", enbd, fuel, 175)
        t(date(2025, 11, 26), "ADNOC Fuel", "ADNOC", enbd, fuel, 195)

        t(date(2025, 11, 3), "Salik Toll", "Salik", enbd, salik, 24)
        t(date(2025, 11, 10), "Salik Toll", "Salik", enbd, salik, 12)
        t(date(2025, 11, 17), "Salik Toll", "Salik", enbd, salik, 24)
        t(date(2025, 11, 24), "Salik Toll", "Salik", enbd, salik, 12)

        t(date(2025, 11, 8), "Parking Marina", "Parking", enbd, parking, 10)

        # Black Friday shopping spree
        t(date(2025, 11, 28), "Black Friday - Clothes", "Namshi", amex, clothes, 780)
        t(date(2025, 11, 28), "Black Friday - Electronics", "Amazon", amex, electronics, 1200)
        t(date(2025, 11, 28), "Black Friday - Home", "Home Centre", visa, home_shopping, 450)

        t(date(2025, 11, 10), "VOX Cinema", "VOX", visa, cinema, 110)
        t(date(2025, 11, 15), "Global Village Tickets", "Global Village", enbd, events, 200)

        t(date(2025, 11, 12), "Pharmacy", "Life Pharmacy", enbd, pharmacy, 95)

        t(date(2025, 11, 5), "Freelance - Website", "Client C", freelance_web, adcb, 5500)
        t(date(2025, 11, 20), "Freelance - Consulting", "Client B", freelance_consult, adcb, 2500)

        t(date(2025, 11, 25), "Visa Payment", None, enbd, visa, 3500)
        t(date(2025, 11, 26), "Amex Payment", None, enbd, amex, 2000)

        t(date(2025, 11, 22), "Birthday Gift", "Virgin Megastore", enbd, gifts, 350)

        # === DECEMBER 2025 ===
        add_monthly_recurring(2025, 12)
        t(date(2025, 12, 2), "Carrefour Groceries", "Carrefour", enbd, groceries, 380)
        t(date(2025, 12, 7), "Lulu Groceries", "Lulu", enbd, groceries, 290)
        t(date(2025, 12, 12), "Spinneys Groceries", "Spinneys", enbd, groceries, 310)
        t(date(2025, 12, 17), "Carrefour Groceries", "Carrefour", enbd, groceries, 420)
        t(date(2025, 12, 22), "Lulu Groceries", "Lulu", enbd, groceries, 350)
        t(date(2025, 12, 28), "Spinneys Groceries", "Spinneys", enbd, groceries, 380)

        t(date(2025, 12, 1), "Coffee", "Starbucks", visa, coffee, 28)
        t(date(2025, 12, 5), "Coffee", "Tim Hortons", enbd, coffee, 22)
        t(date(2025, 12, 10), "Coffee", "Caribou", enbd, coffee, 25)
        t(date(2025, 12, 15), "Coffee", "Starbucks", visa, coffee, 38)
        t(date(2025, 12, 20), "Coffee", "Tim Hortons", enbd, coffee, 20)
        t(date(2025, 12, 26), "Coffee", "Starbucks", visa, coffee, 30)

        t(date(2025, 12, 3), "Dinner", "Nobu", amex, restaurants, 520)
        t(date(2025, 12, 10), "Lunch", "Texas Roadhouse", enbd, restaurants, 130)
        t(date(2025, 12, 18), "Holiday Dinner", "Ossiano", amex, restaurants, 750)
        t(date(2025, 12, 24), "Christmas Eve Dinner", "La Petite Maison", amex, restaurants, 580)
        t(date(2025, 12, 31), "NYE Dinner", "At.Mosphere", amex, restaurants, 1200)

        t(date(2025, 12, 4), "Talabat Order", "Talabat", visa, delivery, 75)
        t(date(2025, 12, 11), "Deliveroo Order", "Deliveroo", visa, delivery, 88)
        t(date(2025, 12, 19), "Talabat Order", "Talabat", visa, delivery, 65)
        t(date(2025, 12, 27), "Noon Food", "Noon", visa, delivery, 70)

        t(date(2025, 12, 3), "ADNOC Fuel", "ADNOC", enbd, fuel, 170)
        t(date(2025, 12, 14), "ENOC Fuel", "ENOC", enbd, fuel, 185)
        t(date(2025, 12, 26), "ADNOC Fuel", "ADNOC", enbd, fuel, 190)

        t(date(2025, 12, 2), "Salik Toll", "Salik", enbd, salik, 24)
        t(date(2025, 12, 9), "Salik Toll", "Salik", enbd, salik, 12)
        t(date(2025, 12, 16), "Salik Toll", "Salik", enbd, salik, 24)
        t(date(2025, 12, 23), "Salik Toll", "Salik", enbd, salik, 12)
        t(date(2025, 12, 30), "Salik Toll", "Salik", enbd, salik, 24)

        t(date(2025, 12, 7), "Parking Festival City", "Parking", enbd, parking, 10)
        t(date(2025, 12, 20), "Parking MOE", "Parking", enbd, parking, 20)

        # Holiday travel — big spending month
        t(date(2025, 12, 15), "Flights to Istanbul", "Emirates", amex, flights, 3200)
        t(date(2025, 12, 20), "Istanbul Hotel", "Booking.com", amex, hotels, 2800)
        t(date(2025, 12, 22), "Istanbul Activities", "Viator", visa, activities, 650)

        # Holiday gifts
        t(date(2025, 12, 10), "Holiday Gifts", "Various", amex, gifts, 1500)
        t(date(2025, 12, 15), "Secret Santa Gift", "Amazon", visa, gifts, 200)

        t(date(2025, 12, 5), "Winter Clothes", "Massimo Dutti", amex, clothes, 650)
        t(date(2025, 12, 12), "VOX Cinema", "VOX", visa, cinema, 85)

        t(date(2025, 12, 8), "Pharmacy", "Aster", enbd, pharmacy, 110)
        t(date(2025, 12, 18), "AC Maintenance", "Cool Tech", enbd, maintenance, 350)

        t(date(2025, 12, 5), "Freelance - Website", "Client A", freelance_web, adcb, 6000)
        t(date(2025, 12, 15), "Dividend - AAPL", "Broker", dividends, stocks, 1200)
        t(date(2025, 12, 20), "Cashback Reward", "ENBD", cashback, enbd, 200)

        t(date(2025, 12, 25), "Visa Payment", None, enbd, visa, 4000)
        t(date(2025, 12, 26), "Amex Payment", None, enbd, amex, 5000)

        # Car insurance annual renewal
        t(date(2025, 12, 1), "Car Insurance Renewal", "AXA", enbd, car_insurance, 3200)

        # Stock purchase
        t(date(2025, 12, 10), "Stock Purchase - ETF", "Broker", enbd, stocks, 5000)

        # === JANUARY 2026 ===
        add_monthly_recurring(2026, 1)
        t(date(2026, 1, 3), "Carrefour Groceries", "Carrefour", enbd, groceries, 310)
        t(date(2026, 1, 8), "Lulu Groceries", "Lulu", enbd, groceries, 265)
        t(date(2026, 1, 13), "Spinneys Groceries", "Spinneys", enbd, groceries, 230)
        t(date(2026, 1, 18), "Carrefour Groceries", "Carrefour", enbd, groceries, 290)
        t(date(2026, 1, 23), "Lulu Groceries", "Lulu", enbd, groceries, 275)
        t(date(2026, 1, 29), "Spinneys Groceries", "Spinneys", enbd, groceries, 255)

        t(date(2026, 1, 2), "Coffee", "Starbucks", visa, coffee, 30)
        t(date(2026, 1, 6), "Coffee", "Tim Hortons", enbd, coffee, 22)
        t(date(2026, 1, 10), "Coffee", "Caribou", enbd, coffee, 25)
        t(date(2026, 1, 14), "Coffee", "Starbucks", visa, coffee, 32)
        t(date(2026, 1, 19), "Coffee", "Tim Hortons", enbd, coffee, 20)
        t(date(2026, 1, 25), "Coffee", "Starbucks", visa, coffee, 28)

        t(date(2026, 1, 4), "Dinner", "Zuma", amex, restaurants, 420)
        t(date(2026, 1, 9), "Lunch", "Nando's", enbd, restaurants, 95)
        t(date(2026, 1, 16), "Friday Brunch", "Waldorf Astoria", visa, restaurants, 450)
        t(date(2026, 1, 24), "Dinner Out", "Tresind", amex, restaurants, 380)

        t(date(2026, 1, 5), "Talabat Order", "Talabat", visa, delivery, 72)
        t(date(2026, 1, 12), "Deliveroo Order", "Deliveroo", visa, delivery, 58)
        t(date(2026, 1, 20), "Talabat Order", "Talabat", visa, delivery, 85)

        t(date(2026, 1, 4), "ADNOC Fuel", "ADNOC", enbd, fuel, 175)
        t(date(2026, 1, 15), "ENOC Fuel", "ENOC", enbd, fuel, 180)
        t(date(2026, 1, 27), "ADNOC Fuel", "ADNOC", enbd, fuel, 185)

        t(date(2026, 1, 3), "Salik Toll", "Salik", enbd, salik, 24)
        t(date(2026, 1, 10), "Salik Toll", "Salik", enbd, salik, 12)
        t(date(2026, 1, 17), "Salik Toll", "Salik", enbd, salik, 24)
        t(date(2026, 1, 24), "Salik Toll", "Salik", enbd, salik, 12)

        t(date(2026, 1, 11), "Parking Dubai Mall", "Emaar", enbd, parking, 5)
        t(date(2026, 1, 18), "Parking JBR", "Parking", enbd, parking, 15)

        t(date(2026, 1, 10), "Massimo Dutti", "Massimo Dutti", amex, clothes, 520)
        t(date(2026, 1, 20), "AirPods", "Apple Store", amex, electronics, 899)

        t(date(2026, 1, 7), "VOX Cinema", "VOX", visa, cinema, 95)
        t(date(2026, 1, 15), "Concert Tickets", "Ticketmaster", visa, events, 450)

        t(date(2026, 1, 8), "Doctor Visit", "Mediclinic", enbd, medical, 500)
        t(date(2026, 1, 22), "Pharmacy", "Life Pharmacy", enbd, pharmacy, 75)

        t(date(2026, 1, 12), "Freelance - Consulting", "Client D", freelance_consult, adcb, 4000)
        t(date(2026, 1, 20), "Cashback Reward", "ENBD", cashback, enbd, 175)

        t(date(2026, 1, 25), "Visa Payment", None, enbd, visa, 3000)
        t(date(2026, 1, 26), "Amex Payment", None, enbd, amex, 3500)

        t(date(2026, 1, 15), "Online Course - Data Science", "Coursera", visa, education, 180)
        t(date(2026, 1, 20), "Crypto Purchase", "Binance", enbd, crypto, 2000)

        # === FEBRUARY 2026 (current month — partial) ===
        add_monthly_recurring(2026, 2)
        t(date(2026, 2, 2), "Carrefour Groceries", "Carrefour", enbd, groceries, 325)
        t(date(2026, 2, 7), "Lulu Groceries", "Lulu", enbd, groceries, 280)
        t(date(2026, 2, 12), "Spinneys Groceries", "Spinneys", enbd, groceries, 195)
        t(date(2026, 2, 17), "Carrefour Groceries", "Carrefour", enbd, groceries, 310)
        t(date(2026, 2, 22), "Lulu Groceries", "Lulu", enbd, groceries, 255)

        t(date(2026, 2, 3), "Coffee", "Starbucks", visa, coffee, 30)
        t(date(2026, 2, 7), "Coffee", "Tim Hortons", enbd, coffee, 22)
        t(date(2026, 2, 11), "Coffee", "Caribou", enbd, coffee, 28)
        t(date(2026, 2, 15), "Coffee", "Starbucks", visa, coffee, 32)
        t(date(2026, 2, 19), "Coffee", "Tim Hortons", enbd, coffee, 20)

        t(date(2026, 2, 4), "Dinner", "Hakkasan", amex, restaurants, 520)
        t(date(2026, 2, 8), "Lunch", "Shake Shack", enbd, restaurants, 85)
        t(date(2026, 2, 14), "Valentine's Dinner", "Pierchic", amex, restaurants, 900)
        t(date(2026, 2, 20), "Friday Brunch", "One&Only", visa, restaurants, 400)

        t(date(2026, 2, 5), "Talabat Order", "Talabat", visa, delivery, 80)
        t(date(2026, 2, 13), "Deliveroo Order", "Deliveroo", visa, delivery, 72)
        t(date(2026, 2, 18), "Talabat Order", "Talabat", visa, delivery, 65)

        t(date(2026, 2, 3), "ADNOC Fuel", "ADNOC", enbd, fuel, 180)
        t(date(2026, 2, 14), "ENOC Fuel", "ENOC", enbd, fuel, 175)
        t(date(2026, 2, 22), "ADNOC Fuel", "ADNOC", enbd, fuel, 190)

        t(date(2026, 2, 2), "Salik Toll", "Salik", enbd, salik, 24)
        t(date(2026, 2, 9), "Salik Toll", "Salik", enbd, salik, 12)
        t(date(2026, 2, 16), "Salik Toll", "Salik", enbd, salik, 24)
        t(date(2026, 2, 23), "Salik Toll", "Salik", enbd, salik, 12)

        t(date(2026, 2, 8), "Parking Marina Mall", "Parking", enbd, parking, 10)
        t(date(2026, 2, 15), "Parking Downtown", "RTA", enbd, parking, 10)

        # Valentine's Day gifts
        t(date(2026, 2, 13), "Valentine's Gift", "Tiffany", amex, gifts, 1200)
        t(date(2026, 2, 14), "Flowers", "Florista", enbd, gifts, 350)

        t(date(2026, 2, 10), "H&M Sale", "H&M", visa, clothes, 280)
        t(date(2026, 2, 18), "VOX Cinema", "VOX", visa, cinema, 95)
        t(date(2026, 2, 6), "Pharmacy", "Aster", enbd, pharmacy, 65)

        t(date(2026, 2, 10), "Freelance - Website", "Client E", freelance_web, adcb, 5000)
        t(date(2026, 2, 15), "Dividend - GOOG", "Broker", dividends, stocks, 950)
        t(date(2026, 2, 20), "Cashback Reward", "ENBD", cashback, enbd, 125)

        t(date(2026, 2, 20), "Visa Payment", None, enbd, visa, 2800)
        t(date(2026, 2, 21), "Amex Payment", None, enbd, amex, 3000)

        t(date(2026, 2, 12), "Plumbing Repair", "Handyman", enbd, maintenance, 450)

        # ── Insert all transactions ───────────────────────────────
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
            (groceries, Decimal("1800")),
            (restaurants, Decimal("1500")),
            (coffee, Decimal("200")),
            (delivery, Decimal("400")),
            (dewa, Decimal("700")),
            (fuel, Decimal("600")),
            (salik, Decimal("120")),
            (parking, Decimal("100")),
            (cinema, Decimal("200")),
            (clothes, Decimal("800")),
            (electronics, Decimal("500")),
            (home_shopping, Decimal("500")),
            (streaming, Decimal("150")),
            (pharmacy, Decimal("200")),
            (gifts, Decimal("500")),
        ]

        for account_id, amount in budget_data:
            budget_service.create_budget(
                account_id=account_id,
                amount=amount,
                period="monthly",
            )

    n_txn = len(transactions)
    n_bgt = len(budget_data)
    print(f"Demo database seeded: {n_txn} transactions, {n_bgt} budgets, 6 months of data")
