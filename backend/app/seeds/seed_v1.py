"""Seed script for v1 MVP data."""
import sys
import os
from datetime import date
import argparse

# Add the backend directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from sqlalchemy.orm import sessionmaker
from app.db import engine, enable_foreign_keys
from app.models import Account, Instrument, Price, Transaction, TransactionLine


def seed_accounts(session, force=False):
    """Seed minimal chart of accounts."""
    accounts_data = [
        {"name": "Assets:Cash", "type": "ASSET", "currency": "USD"},
        {"name": "Assets:Brokerage", "type": "ASSET", "currency": "USD"},
        {"name": "Income:Dividends", "type": "INCOME", "currency": "USD"},
        {"name": "Expenses:Fees", "type": "EXPENSE", "currency": "USD"},
        {"name": "Equity:Opening Balance", "type": "EQUITY", "currency": "USD"},
    ]
    
    for account_data in accounts_data:
        # Check if account already exists
        existing = session.query(Account).filter_by(name=account_data["name"]).first()
        if not existing:
            account = Account(**account_data)
            session.add(account)
            print(f"Added account: {account_data['name']}")
        else:
            if force:
                print(f"Account already exists (force mode): {account_data['name']}")
            else:
                print(f"Account already exists: {account_data['name']}")


def seed_instruments(session):
    """Seed sample instruments."""
    instruments_data = [
        {"symbol": "AAPL", "name": "Apple Inc.", "type": "EQUITY", "currency": "USD"},
        {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "type": "ETF", "currency": "USD"},
    ]
    
    for instrument_data in instruments_data:
        # Check if instrument already exists
        existing = session.query(Instrument).filter_by(symbol=instrument_data["symbol"]).first()
        if not existing:
            instrument = Instrument(**instrument_data)
            session.add(instrument)
            print(f"Added instrument: {instrument_data['symbol']}")
        else:
            print(f"Instrument already exists: {instrument_data['symbol']}")


def seed_prices(session):
    """Seed sample prices for today."""
    today = date.today().isoformat()
    
    # Sample prices for today
    prices_data = [
        {"symbol": "AAPL", "price": 150.00},
        {"symbol": "SPY", "price": 430.00},
    ]
    
    for price_data in prices_data:
        # Get the instrument
        instrument = session.query(Instrument).filter_by(symbol=price_data["symbol"]).first()
        if instrument:
            # Check if price already exists for today
            existing = session.query(Price).filter_by(
                instrument_id=instrument.id, 
                date=today
            ).first()
            if not existing:
                price = Price(
                    instrument_id=instrument.id,
                    date=today,
                    close=price_data["price"]
                )
                session.add(price)
                print(f"Added price for {price_data['symbol']}: ${price_data['price']}")
            else:
                print(f"Price already exists for {price_data['symbol']} on {today}")


def seed_opening_balance(session):
    """Create an opening balance transaction that zero-balances."""
    # Check if opening balance transaction already exists
    existing = session.query(Transaction).filter_by(
        type="ADJUST",
        memo="Opening Balance"
    ).first()
    
    if existing:
        print("Opening balance transaction already exists")
        return
    
    # Get accounts
    cash_account = session.query(Account).filter_by(name="Assets:Cash").first()
    equity_account = session.query(Account).filter_by(name="Equity:Opening Balance").first()
    
    if not cash_account or not equity_account:
        print("Required accounts not found for opening balance")
        return
    
    today = date.today().isoformat()
    
    # Create opening balance transaction
    transaction = Transaction(
        date=today,
        type="ADJUST",
        memo="Opening Balance",
        posted=1  # Post it immediately since it's balanced
    )
    session.add(transaction)
    session.flush()  # Get the transaction ID
    
    # Create balanced transaction lines
    # Debit cash $1000
    cash_line = TransactionLine(
        transaction_id=transaction.id,
        account_id=cash_account.id,
        amount=1000.00,
        dr_cr="DR"
    )
    session.add(cash_line)
    
    # Credit equity $1000
    equity_line = TransactionLine(
        transaction_id=transaction.id,
        account_id=equity_account.id,
        amount=1000.00,
        dr_cr="CR"
    )
    session.add(equity_line)
    
    print("Added opening balance transaction: $1000")


def run_seeds():
    """Run all seed functions."""
    # Create session
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("Starting seed process...")
        
        # Seed data
        seed_accounts(session)
        seed_instruments(session)
        seed_prices(session)
        seed_opening_balance(session)
        
        # Commit all changes
        session.commit()
        print("Seed process completed successfully!")
        
    except Exception as e:
        session.rollback()
        print(f"Error during seeding: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    run_seeds()