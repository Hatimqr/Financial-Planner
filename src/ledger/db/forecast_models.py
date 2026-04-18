"""SQLAlchemy models for the forecasting module.

Kept separate from :mod:`ledger.db.models` to reinforce the design principle
that forecast tables are completely independent of the ledger — they do not
reference ``accounts.id`` or any other ledger table. ``Base`` is shared so
a single ``Base.metadata`` drives both Alembic and ``create_all`` in tests.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ledger.db.models import Base


class ForecastProfile(Base):
    """A self-contained cashflow model for one life situation."""

    __tablename__ = "forecast_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    horizon_months: Mapped[int] = mapped_column(Integer, nullable=False)
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, onupdate=datetime.utcnow
    )

    lines: Mapped[list["ForecastLine"]] = relationship(
        "ForecastLine",
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="ForecastLine.sort_order",
    )

    __table_args__ = (
        CheckConstraint("horizon_months > 0", name="ck_forecast_profile_horizon"),
    )

    def __repr__(self) -> str:
        return (
            f"<ForecastProfile(id={self.id}, name='{self.name}', "
            f"currency='{self.currency}', horizon_months={self.horizon_months})>"
        )


class ForecastLine(Base):
    """One recurring monthly cash delta within a profile."""

    __tablename__ = "forecast_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("forecast_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    start_month_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_month_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    profile: Mapped["ForecastProfile"] = relationship(
        "ForecastProfile", back_populates="lines"
    )
    overrides: Mapped[list["ForecastLineOverride"]] = relationship(
        "ForecastLineOverride",
        back_populates="line",
        cascade="all, delete-orphan",
        order_by="ForecastLineOverride.month_offset",
    )

    __table_args__ = (
        CheckConstraint(
            "kind IN ('inflow', 'outflow')", name="ck_forecast_line_kind"
        ),
        CheckConstraint("amount >= 0", name="ck_forecast_line_amount"),
        CheckConstraint(
            "start_month_offset >= 0", name="ck_forecast_line_start_offset"
        ),
        CheckConstraint(
            "end_month_offset >= start_month_offset",
            name="ck_forecast_line_end_offset",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ForecastLine(id={self.id}, profile_id={self.profile_id}, "
            f"label='{self.label}', kind='{self.kind}', amount={self.amount})>"
        )


class ForecastLineOverride(Base):
    """A per-month absolute-amount override for one line.

    When present, replaces the base line ``amount`` for the given
    ``month_offset`` during projection. Sign (``kind``) is inherited
    from the parent line. Sparse: lines may have zero or more overrides.
    """

    __tablename__ = "forecast_line_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    line_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("forecast_lines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    month_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    line: Mapped["ForecastLine"] = relationship(
        "ForecastLine", back_populates="overrides"
    )

    __table_args__ = (
        CheckConstraint(
            "month_offset >= 0", name="ck_forecast_line_override_month_offset"
        ),
        CheckConstraint("amount >= 0", name="ck_forecast_line_override_amount"),
        UniqueConstraint(
            "line_id", "month_offset", name="uq_forecast_line_override_line_month"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ForecastLineOverride(id={self.id}, line_id={self.line_id}, "
            f"month_offset={self.month_offset}, amount={self.amount})>"
        )
