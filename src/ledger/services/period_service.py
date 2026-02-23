"""Period service for managing time periods across all screens."""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from ledger.db.models import AppSettings, TimePeriod


@dataclass
class ResolvedPeriod:
    """A period resolved to concrete start/end dates."""
    key: str          # Unique identifier (e.g. "this-month", "custom-3")
    label: str        # Display label
    start_date: date
    end_date: date
    is_builtin: bool = True
    db_id: Optional[int] = None  # For custom periods


# Built-in period definitions (always available, not stored in DB)
BUILTIN_PERIODS = [
    ("all", "All"),
    ("this-month", "This Month"),
    ("last-month", "Last Month"),
]

# Default period key used on startup (can be overridden by user setting)
DEFAULT_PERIOD_KEY = "this-month"

# Supported relative period keys and their labels
RELATIVE_PRESETS = {
    "last_7_days": "Last 7 Days",
    "last_14_days": "Last 14 Days",
    "last_30_days": "Last 30 Days",
    "last_90_days": "Last 90 Days",
    "last_6_months": "Last 6 Months",
    "this_quarter": "This Quarter",
    "last_quarter": "Last Quarter",
    "this_week": "This Week",
}


def resolve_builtin(key: str) -> tuple[date, date]:
    """Resolve a built-in period key to start/end dates."""
    today = date.today()

    if key == "all":
        return date(2000, 1, 1), today
    elif key == "this-month":
        return today.replace(day=1), today
    elif key == "last-month":
        first_of_current = today.replace(day=1)
        end = first_of_current - timedelta(days=1)
        return end.replace(day=1), end
    else:
        raise ValueError(f"Unknown built-in period: {key}")


def resolve_relative(relative_key: str) -> tuple[date, date]:
    """Resolve a relative period key to start/end dates."""
    today = date.today()

    if relative_key == "last_7_days":
        return today - timedelta(days=6), today
    elif relative_key == "last_14_days":
        return today - timedelta(days=13), today
    elif relative_key == "last_30_days":
        return today - timedelta(days=29), today
    elif relative_key == "last_90_days":
        return today - timedelta(days=89), today
    elif relative_key == "last_6_months":
        month = today.month - 6
        year = today.year
        while month < 1:
            month += 12
            year -= 1
        start = date(year, month, 1)
        return start, today
    elif relative_key == "this_quarter":
        q_start_month = ((today.month - 1) // 3) * 3 + 1
        return date(today.year, q_start_month, 1), today
    elif relative_key == "last_quarter":
        q_start_month = ((today.month - 1) // 3) * 3 + 1
        q_start = date(today.year, q_start_month, 1)
        end = q_start - timedelta(days=1)
        prev_q_start_month = ((end.month - 1) // 3) * 3 + 1
        return date(end.year, prev_q_start_month, 1), end
    elif relative_key == "this_week":
        start = today - timedelta(days=today.weekday())  # Monday
        return start, today
    else:
        raise ValueError(f"Unknown relative period: {relative_key}")


class PeriodService:
    """Service for managing custom time periods."""

    def __init__(self, session: Session):
        self.session = session

    def get_custom_periods(self) -> List[TimePeriod]:
        """Get all custom periods ordered by sort_order."""
        return (
            self.session.query(TimePeriod)
            .order_by(TimePeriod.sort_order, TimePeriod.id)
            .all()
        )

    def create_period(
        self,
        label: str,
        period_type: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        relative_key: Optional[str] = None,
    ) -> TimePeriod:
        """Create a new custom period."""
        if period_type == "fixed":
            if not start_date or not end_date:
                raise ValueError("Fixed periods require start_date and end_date")
            if start_date > end_date:
                raise ValueError("start_date must be before end_date")
        elif period_type == "relative":
            if not relative_key or relative_key not in RELATIVE_PRESETS:
                raise ValueError(f"Invalid relative_key. Must be one of: {', '.join(RELATIVE_PRESETS.keys())}")
        else:
            raise ValueError("period_type must be 'fixed' or 'relative'")

        # Get next sort_order
        max_order = (
            self.session.query(TimePeriod.sort_order)
            .order_by(TimePeriod.sort_order.desc())
            .first()
        )
        next_order = (max_order[0] + 1) if max_order else 0

        period = TimePeriod(
            label=label,
            period_type=period_type,
            start_date=start_date,
            end_date=end_date,
            relative_key=relative_key,
            sort_order=next_order,
        )
        self.session.add(period)
        self.session.flush()
        return period

    def update_period(
        self,
        period_id: int,
        label: Optional[str] = None,
        period_type: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        relative_key: Optional[str] = None,
    ) -> TimePeriod:
        """Update an existing custom period."""
        period = self.session.query(TimePeriod).get(period_id)
        if not period:
            raise ValueError(f"Period with ID {period_id} not found")

        if label is not None:
            period.label = label
        if period_type is not None:
            period.period_type = period_type
        if start_date is not None:
            period.start_date = start_date
        if end_date is not None:
            period.end_date = end_date
        if relative_key is not None:
            period.relative_key = relative_key

        self.session.flush()
        return period

    def delete_period(self, period_id: int) -> None:
        """Delete a custom period."""
        period = self.session.query(TimePeriod).get(period_id)
        if not period:
            raise ValueError(f"Period with ID {period_id} not found")
        self.session.delete(period)
        self.session.flush()

    def resolve_period(self, period: TimePeriod) -> ResolvedPeriod:
        """Resolve a custom TimePeriod to concrete dates."""
        if period.period_type == "fixed":
            return ResolvedPeriod(
                key=f"custom-{period.id}",
                label=period.label,
                start_date=period.start_date,
                end_date=period.end_date,
                is_builtin=False,
                db_id=period.id,
            )
        else:
            start, end = resolve_relative(period.relative_key)
            return ResolvedPeriod(
                key=f"custom-{period.id}",
                label=period.label,
                start_date=start,
                end_date=end,
                is_builtin=False,
                db_id=period.id,
            )

    def get_all_resolved_periods(self) -> List[ResolvedPeriod]:
        """Get all periods (built-in + custom) resolved to concrete dates."""
        periods = []

        # Built-in periods
        for key, label in BUILTIN_PERIODS:
            start, end = resolve_builtin(key)
            periods.append(ResolvedPeriod(
                key=key, label=label, start_date=start, end_date=end, is_builtin=True
            ))

        # Custom periods
        for custom in self.get_custom_periods():
            periods.append(self.resolve_period(custom))

        return periods

    def _get_or_create_settings(self) -> AppSettings:
        """Get or create the singleton settings row."""
        settings = self.session.query(AppSettings).first()
        if not settings:
            settings = AppSettings(id=1, default_period_key=DEFAULT_PERIOD_KEY)
            self.session.add(settings)
            self.session.flush()
        return settings

    def get_default_period_key(self) -> str:
        """Get the user's chosen default period key."""
        settings = self._get_or_create_settings()
        return settings.default_period_key

    def set_default_period_key(self, key: str) -> None:
        """Set the default period key."""
        # Validate the key exists
        all_valid = [k for k, _ in BUILTIN_PERIODS]
        for custom in self.get_custom_periods():
            all_valid.append(f"custom-{custom.id}")
        if key not in all_valid:
            raise ValueError(f"Unknown period key: {key}")

        settings = self._get_or_create_settings()
        settings.default_period_key = key
        self.session.flush()
