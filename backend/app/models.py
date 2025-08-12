"""SQLAlchemy ORM models mirroring the MVP schema."""
from sqlalchemy import Column, Integer, Text, REAL, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db import Base


class Account(Base):
    """Account model for chart of accounts."""
    __tablename__ = 'accounts'

    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    type = Column(Text, nullable=False)
    currency = Column(Text, nullable=False)

    # Relationships
    transaction_lines = relationship("TransactionLine", back_populates="account")
    lots = relationship("Lot", back_populates="account")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "type IN ('ASSET','LIABILITY','INCOME','EXPENSE','EQUITY')",
            name='ck_account_type'
        ),
    )


class Instrument(Base):
    """Instrument model for tradeable securities."""
    __tablename__ = 'instruments'

    id = Column(Integer, primary_key=True)
    symbol = Column(Text, nullable=False, unique=True)
    name = Column(Text, nullable=False)
    type = Column(Text, nullable=False)
    currency = Column(Text, nullable=False)

    # Relationships
    prices = relationship("Price", back_populates="instrument", cascade="all, delete-orphan")
    transaction_lines = relationship("TransactionLine", back_populates="instrument")
    lots = relationship("Lot", back_populates="instrument")
    corporate_actions = relationship("CorporateAction", back_populates="instrument")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "type IN ('EQUITY','ETF','BOND','CASH','CRYPTO')",
            name='ck_instrument_type'
        ),
    )


class Price(Base):
    """Price model for instrument pricing data."""
    __tablename__ = 'prices'

    instrument_id = Column(Integer, ForeignKey('instruments.id', ondelete='CASCADE'), primary_key=True)
    date = Column(Text, primary_key=True)
    close = Column(REAL, nullable=False)

    # Relationships
    instrument = relationship("Instrument", back_populates="prices")

    # Indexes
    __table_args__ = (
        Index('idx_prices_date', 'date'),
    )


class Transaction(Base):
    """Transaction model for double-entry transactions."""
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True)
    date = Column(Text, nullable=False)
    type = Column(Text, nullable=False)
    memo = Column(Text)
    posted = Column(Integer, nullable=False, default=0)
    created_at = Column(Text, nullable=False, server_default=func.strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))

    # Relationships
    lines = relationship("TransactionLine", back_populates="transaction", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "type IN ('TRADE','TRANSFER','DIVIDEND','FEE','TAX','FX','ADJUST')",
            name='ck_transaction_type'
        ),
        CheckConstraint(
            "posted IN (0,1)",
            name='ck_transaction_posted'
        ),
    )


class TransactionLine(Base):
    """Transaction line model for individual entries in double-entry system."""
    __tablename__ = 'transaction_lines'

    id = Column(Integer, primary_key=True)
    transaction_id = Column(Integer, ForeignKey('transactions.id', ondelete='CASCADE'), nullable=False)
    account_id = Column(Integer, ForeignKey('accounts.id', ondelete='RESTRICT'), nullable=False)
    instrument_id = Column(Integer, ForeignKey('instruments.id', ondelete='RESTRICT'), nullable=True)
    quantity = Column(REAL)
    amount = Column(REAL, nullable=False)
    dr_cr = Column(Text, nullable=False)

    # Relationships
    transaction = relationship("Transaction", back_populates="lines")
    account = relationship("Account", back_populates="transaction_lines")
    instrument = relationship("Instrument", back_populates="transaction_lines")

    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint(
            "dr_cr IN ('DR','CR')",
            name='ck_transaction_line_dr_cr'
        ),
        Index('idx_tl_tx', 'transaction_id'),
        Index('idx_tl_acct', 'account_id'),
    )


class Lot(Base):
    """Lot model for position tracking."""
    __tablename__ = 'lots'

    id = Column(Integer, primary_key=True)
    instrument_id = Column(Integer, ForeignKey('instruments.id'), nullable=False)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    open_date = Column(Text, nullable=False)
    qty_opened = Column(REAL, nullable=False)
    qty_closed = Column(REAL, nullable=False, default=0)
    cost_total = Column(REAL, nullable=False)
    closed = Column(Integer, nullable=False, default=0)

    # Relationships
    instrument = relationship("Instrument", back_populates="lots")
    account = relationship("Account", back_populates="lots")

    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("qty_closed >= 0", name='ck_lot_qty_closed'),
        CheckConstraint("closed IN (0,1)", name='ck_lot_closed'),
        Index('idx_lots_open', 'open_date'),
    )


class CorporateAction(Base):
    """Corporate action model for tracking splits, dividends, and symbol changes."""
    __tablename__ = 'corporate_actions'

    id = Column(Integer, primary_key=True)
    instrument_id = Column(Integer, ForeignKey('instruments.id', ondelete='RESTRICT'), nullable=False)
    type = Column(Text, nullable=False)
    date = Column(Text, nullable=False)
    ratio = Column(REAL)  # For splits (e.g., 2.0 for 2:1 split)
    cash_per_share = Column(REAL)  # For dividends (cash amount per share)
    notes = Column(Text)
    processed = Column(Integer, nullable=False, default=0)
    created_at = Column(Text, nullable=False, server_default=func.strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))

    # Relationships
    instrument = relationship("Instrument", back_populates="corporate_actions")

    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint(
            "type IN ('SPLIT','CASH_DIVIDEND','STOCK_DIVIDEND','SYMBOL_CHANGE','MERGER','SPINOFF')",
            name='ck_corporate_action_type'
        ),
        CheckConstraint(
            "processed IN (0,1)",
            name='ck_corporate_action_processed'
        ),
        Index('idx_ca_instrument', 'instrument_id'),
        Index('idx_ca_date', 'date'),
    )