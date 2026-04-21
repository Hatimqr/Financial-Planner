"""Hardcoded UK tax band tables (Scotland income tax, rUK income tax, UK NI).

Bands are stored as ``ProgressiveTaxBands``: an allowance amount plus a list
of ``(upper_bound_above_allowance, rate)`` tuples. The band engine walks
these sequentially — see ``tax_engine.compute_progressive_tax``.

Values reflect published UK/Scottish Budget figures for the 2025-26 tax
year. rUK bands remain stable across recent years; Scottish bands change
annually. NI monthly thresholds are stored directly (NI is non-cumulative
per pay period, so monthly math is native).

When a tax year is requested that isn't in a table, the engine falls back
to the latest known year and flags a ``ProjectionWarning``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ProgressiveTaxBands:
    """A progressive tax table.

    ``bands`` is a list of ``(upper_bound_above_allowance, rate)`` pairs.
    The last band should use ``Decimal("Infinity")`` as its upper bound.
    Rates are decimal fractions (e.g. ``Decimal("0.19")`` for 19%).

    For income tax, ``personal_allowance`` is the tax-free PA and
    ``pa_taper_threshold`` (when set) activates the £1-per-£2 taper rule.
    For NI, ``personal_allowance`` acts as the Primary Threshold and
    ``pa_taper_threshold`` is None.
    """

    personal_allowance: Decimal
    bands: tuple[tuple[Decimal, Decimal], ...]
    pa_taper_threshold: Decimal | None = None
    pa_taper_divisor: Decimal = Decimal("2")


_INF = Decimal("Infinity")


# Scottish income tax 2025-26 (annual, post-PA).
# Source: Scottish Government 2025-26 Budget.
SCOTLAND_INCOME_TAX: dict[str, ProgressiveTaxBands] = {
    "2025-26": ProgressiveTaxBands(
        personal_allowance=Decimal("12570"),
        bands=(
            (Decimal("2306"), Decimal("0.19")),    # Starter: next £2,306
            (Decimal("13991"), Decimal("0.20")),   # Basic:   next £11,685
            (Decimal("31092"), Decimal("0.21")),   # Intermediate: next £17,101
            (Decimal("62430"), Decimal("0.42")),   # Higher:  next £31,338
            (Decimal("112570"), Decimal("0.45")),  # Advanced: next £50,140
            (_INF, Decimal("0.48")),               # Top:     remainder
        ),
        pa_taper_threshold=Decimal("100000"),
    ),
}


# Rest-of-UK income tax 2025-26 (annual, post-PA).
RUK_INCOME_TAX: dict[str, ProgressiveTaxBands] = {
    "2025-26": ProgressiveTaxBands(
        personal_allowance=Decimal("12570"),
        bands=(
            (Decimal("37700"), Decimal("0.20")),   # Basic:      next £37,700
            (Decimal("112570"), Decimal("0.40")),  # Higher:     next £74,870
            (_INF, Decimal("0.45")),               # Additional: remainder
        ),
        pa_taper_threshold=Decimal("100000"),
    ),
}


# UK employee NI (Class 1), 2025-26 (monthly thresholds — non-cumulative).
# PT = Primary Threshold (£1,048/mo = £12,570/yr), UEL = Upper Earnings Limit
# (£4,189/mo = £50,270/yr). Main rate 8% between PT and UEL; 2% above UEL.
# Modelled as a progressive table with PT acting as the "allowance".
NI_EMPLOYEE: dict[str, ProgressiveTaxBands] = {
    "2025-26": ProgressiveTaxBands(
        personal_allowance=Decimal("1048"),  # monthly Primary Threshold
        bands=(
            (Decimal("3141"), Decimal("0.08")),  # UEL - PT = £4,189 - £1,048
            (_INF, Decimal("0.02")),
        ),
        pa_taper_threshold=None,
    ),
}


_KNOWN_TAX_YEARS = ("2025-26",)


def _latest_known_year() -> str:
    return _KNOWN_TAX_YEARS[-1]


def get_income_tax_bands(
    jurisdiction: str, tax_year: str
) -> tuple[ProgressiveTaxBands, bool]:
    """Look up income tax bands. Returns ``(bands, is_fallback)``.

    Falls back to the latest known year when the requested one is missing.
    """
    table = _income_tax_table_for(jurisdiction)
    if tax_year in table:
        return table[tax_year], False
    fallback = _latest_known_year()
    return table[fallback], True


def get_ni_bands(tax_year: str) -> tuple[ProgressiveTaxBands, bool]:
    """Look up NI bands. Returns ``(bands, is_fallback)``."""
    if tax_year in NI_EMPLOYEE:
        return NI_EMPLOYEE[tax_year], False
    return NI_EMPLOYEE[_latest_known_year()], True


def _income_tax_table_for(jurisdiction: str) -> dict[str, ProgressiveTaxBands]:
    if jurisdiction == "scotland":
        return SCOTLAND_INCOME_TAX
    if jurisdiction == "ruk":
        return RUK_INCOME_TAX
    raise ValueError(f"Unknown jurisdiction: {jurisdiction!r}")
