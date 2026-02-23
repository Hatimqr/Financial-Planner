"""SQLAlchemy models for double-entry accounting."""

from datetime import date, datetime
from decimal import Decimal
from typing import List

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class Account(Base):
    """Account model representing the chart of accounts."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    is_placeholder: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    postings: Mapped[List["Posting"]] = relationship(
        "Posting", back_populates="account", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "type IN ('asset', 'liability', 'equity', 'income', 'expense')",
            name="ck_account_type",
        ),
    )

    @property
    def depth(self) -> int:
        """Account depth in hierarchy (0 for top-level)."""
        return self.name.count(":")

    @property
    def leaf_name(self) -> str:
        """Just the account name without parent path."""
        return self.name.split(":")[-1]

    @property
    def parent_name(self) -> str | None:
        """Parent account name."""
        parts = self.name.split(":")
        return ":".join(parts[:-1]) if len(parts) > 1 else None

    @property
    def is_leaf(self) -> bool:
        """Is this a leaf account (non-placeholder, can have transactions)."""
        return not self.is_placeholder

    def __repr__(self) -> str:
        return f"<Account(id={self.id}, name='{self.name}', type='{self.type}')>"


class Entry(Base):
    """Entry model representing a journal entry (transaction header)."""

    __tablename__ = "entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    payee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="cleared")
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, onupdate=datetime.utcnow)

    # Relationships
    postings: Mapped[List["Posting"]] = relationship(
        "Posting", back_populates="entry", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'cleared', 'reconciled')", name="ck_entry_status"
        ),
    )

    def __repr__(self) -> str:
        return f"<Entry(id={self.id}, date={self.date}, description='{self.description}')>"


class Posting(Base):
    """Posting model representing a line item in a journal entry."""

    __tablename__ = "postings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("accounts.id"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False
    )  # Positive = debit, Negative = credit
    memo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    entry: Mapped["Entry"] = relationship("Entry", back_populates="postings")
    account: Mapped["Account"] = relationship("Account", back_populates="postings")

    def __repr__(self) -> str:
        return (
            f"<Posting(id={self.id}, entry_id={self.entry_id}, "
            f"account_id={self.account_id}, amount={self.amount})>"
        )


class Budget(Base):
    """Budget model for tracking spending limits by category."""

    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("accounts.id"), nullable=False, index=True
    )
    period: Mapped[str] = mapped_column(String(20), nullable=False, default="monthly")
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationships
    account: Mapped["Account"] = relationship("Account")

    __table_args__ = (
        CheckConstraint(
            "period IN ('monthly', 'quarterly', 'yearly')", name="ck_budget_period"
        ),
    )

    def __repr__(self) -> str:
        return f"<Budget(id={self.id}, account_id={self.account_id}, amount={self.amount})>"


class TimePeriod(Base):
    """Custom time period for filtering across all screens."""

    __tablename__ = "time_periods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    period_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "fixed" or "relative"
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # For fixed periods
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # For fixed periods
    relative_key: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g. "last_7_days"
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "period_type IN ('fixed', 'relative')", name="ck_time_period_type"
        ),
    )

    def __repr__(self) -> str:
        return f"<TimePeriod(id={self.id}, label='{self.label}', type='{self.period_type}')>"


class AppSettings(Base):
    """Single-row app settings table."""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    default_period_key: Mapped[str] = mapped_column(
        String(100), nullable=False, default="this-month"
    )

    def __repr__(self) -> str:
        return f"<AppSettings(default_period_key='{self.default_period_key}')>"


# Note: Double-entry balance validation is performed in the service layer
# A database trigger would fire after each posting insert, causing false positives
# when inserting multiple postings for a single entry. Instead, we validate the
# complete transaction in TransactionService before committing.
