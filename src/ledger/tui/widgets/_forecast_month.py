"""Shared month-parsing helpers for forecasting forms.

Profiles anchor on the 1st of a given month; lines and overrides store
month offsets relative to that anchor. This module centralises the
user-facing `YYYY-MM` parsing and the offset ↔ (year, month) arithmetic
so all three forecasting forms + the detail header agree on the
conversion.
"""

from __future__ import annotations


_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def try_parse_month(value: str) -> tuple[int, int] | None:
    """Parse a ``YYYY-MM`` string. Return ``(year, month)`` or ``None``.

    Strict: rejects anything that isn't exactly 7 chars in ``YYYY-MM``
    with digits only and ``1 ≤ month ≤ 12``.
    """
    text = (value or "").strip()
    if len(text) != 7 or text[4] != "-":
        return None
    year_str, month_str = text[:4], text[5:]
    if not year_str.isdigit() or not month_str.isdigit():
        return None
    year = int(year_str)
    month = int(month_str)
    if year < 1 or not (1 <= month <= 12):
        return None
    return year, month


def month_name_label(year: int, month: int) -> str:
    """`(2026, 6) -> "June 2026"` — for live input helpers."""
    return f"{_MONTH_NAMES[month - 1]} {year}"


def offset_to_year_month(
    start_year: int, start_month: int, offset: int
) -> tuple[int, int]:
    """Absolute (year, month) of the Nth month from a profile's start.

    `offset=0` returns the profile's own (start_year, start_month).
    """
    total = start_month - 1 + offset
    return (start_year + total // 12, total % 12 + 1)


def offset_to_ym_label(
    start_year: int, start_month: int, offset: int
) -> str:
    """`YYYY-MM` label for a month offset — DataTable cell formatter."""
    y, m = offset_to_year_month(start_year, start_month, offset)
    return f"{y:04d}-{m:02d}"


def year_month_to_offset(
    start_year: int, start_month: int, year: int, month: int
) -> int:
    """Inverse of :func:`offset_to_year_month`.

    Returns a signed offset; callers are responsible for range-checking
    against the profile's ``horizon_months``.
    """
    return (year - start_year) * 12 + (month - start_month)
