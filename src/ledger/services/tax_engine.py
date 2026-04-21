"""Pure tax-calculation helpers for UK income tax + employee NI.

Keep this module free of SQLAlchemy, Alembic, Textual, and any state — it
takes primitives + a ``TaxProfile``-shaped input and returns a per-month
``(income_tax, ni)`` map plus a list of warnings. Unit-tested in isolation.

Design notes
------------
* Income tax is cumulative across a UK tax year (April 6 → April 5). We
  treat the tax-year boundary as April 1 at monthly granularity — more
  than sufficient for planning.
* NI is non-cumulative; it's computed per month on that month's gross
  using monthly thresholds (see ``tax_tables.NI_EMPLOYEE``).
* Mid-year starts use the full annual PA against partial-year gross
  (matches HMRC PAYE for mid-year starters on arising basis).
* Within a tax year, annual IT is divided evenly across the months the
  salary is active in that year. Any rounding residual lands on the last
  month so the per-line sum equals ``compute_progressive_tax`` to the penny.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable

from ledger.services.tax_tables import (
    ProgressiveTaxBands,
    get_income_tax_bands,
    get_ni_bands,
)
from ledger.tui.widgets._forecast_month import offset_to_year_month

_ZERO = Decimal("0")


def tax_year_key(calendar_year: int, calendar_month: int) -> str:
    """UK tax year key for a (year, month) — 'YYYY-YY' style, e.g. '2026-27'.

    Month-granularity cutoff: months April through December belong to the
    tax year starting that April; January through March belong to the tax
    year starting the previous April.
    """
    start = calendar_year if calendar_month >= 4 else calendar_year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def _apply_personal_allowance(
    earnings: Decimal, bands: ProgressiveTaxBands
) -> Decimal:
    """Compute the effective PA after tapering (if configured)."""
    pa = bands.personal_allowance
    if bands.pa_taper_threshold is None or earnings <= bands.pa_taper_threshold:
        return pa
    reduction = (earnings - bands.pa_taper_threshold) / bands.pa_taper_divisor
    return max(pa - reduction, _ZERO)


def compute_progressive_tax(
    earnings: Decimal, bands: ProgressiveTaxBands
) -> Decimal:
    """Walk ``bands`` to compute tax on ``earnings``.

    Applies the allowance (with tapering, if set) first, then taxes the
    remainder progressively. Returns 0 if earnings ≤ 0 or fully absorbed
    by the allowance.
    """
    if earnings <= _ZERO:
        return _ZERO

    allowance = _apply_personal_allowance(earnings, bands)
    taxable = max(earnings - allowance, _ZERO)
    if taxable <= _ZERO:
        return _ZERO

    tax = _ZERO
    remaining = taxable
    previous_upper = _ZERO
    for upper, rate in bands.bands:
        if remaining <= _ZERO:
            break
        band_width = upper - previous_upper
        portion = remaining if remaining < band_width else band_width
        tax += portion * rate
        remaining -= portion
        previous_upper = upper
    return tax


def group_months_by_tax_year(
    profile_start_date: date, month_offsets: Iterable[int]
) -> dict[str, list[int]]:
    """Bucket month offsets by their UK tax year key."""
    out: dict[str, list[int]] = {}
    for m in month_offsets:
        y, mth = offset_to_year_month(
            profile_start_date.year, profile_start_date.month, m
        )
        out.setdefault(tax_year_key(y, mth), []).append(m)
    # Preserve deterministic ordering within each bucket.
    for key in out:
        out[key].sort()
    return out


def compute_line_tax(
    profile_start_date: date,
    monthly_gross_by_offset: dict[int, Decimal],
    base_monthly_amount: Decimal,
    jurisdiction: str,
    apply_income_tax: bool,
    apply_ni: bool,
) -> tuple[dict[int, tuple[Decimal, Decimal]], list[str]]:
    """Compute per-month (income_tax, ni) for one taxed line.

    Parameters
    ----------
    profile_start_date
        The forecast profile's start date (anchors month offsets to calendar
        months).
    monthly_gross_by_offset
        Map of month_offset → gross for months the line is active. Months
        outside the line's window should not appear here. Overridden (e.g.
        bonus) amounts should already be baked in.
    base_monthly_amount
        The line's base per-month amount (pre-override). Used to compute a
        "baseline" income tax that non-override months pay; override months
        absorb the delta. This matches the user-intuition that a one-off
        bonus should only inflate that month's tax, not spread across the
        year.
    jurisdiction
        'scotland' or 'ruk'.
    apply_income_tax, apply_ni
        Toggles from the attached tax profile.

    Returns
    -------
    ({offset: (income_tax, ni)}, warnings)
        ``warnings`` is non-empty when a tax-table fallback occurred.

    Income-tax distribution algorithm
    ---------------------------------
    Per tax year:
      1. ``base_gross`` = ``base_monthly × active_months_in_year``
      2. ``base_IT`` = tax on base_gross (with full PA).
      3. ``actual_IT`` = tax on actual (override-adjusted) gross.
      4. ``delta_IT`` = actual_IT − base_IT.
      5. Each non-override month pays ``base_IT / active_months`` (i.e.
         the figure that month would pay if the whole year ran at base).
      6. Each override month additionally absorbs its proportional share of
         ``delta_IT`` (proportional to ``gross − base``).
      7. Edge: when deviations cancel (total_dev = 0 but individual ones
         nonzero), fall back to proportional-to-gross to keep the totals
         consistent. Per-month IT is clamped at zero.
    """
    result: dict[int, tuple[Decimal, Decimal]] = {
        m: (_ZERO, _ZERO) for m in monthly_gross_by_offset
    }
    warnings: list[str] = []
    warned_years: set[str] = set()

    if not monthly_gross_by_offset:
        return result, warnings

    # Income tax: aggregate per tax year, allocate base-plus-delta.
    if apply_income_tax:
        by_year = group_months_by_tax_year(
            profile_start_date, monthly_gross_by_offset.keys()
        )
        for year_key, offsets in by_year.items():
            bands, is_fallback = get_income_tax_bands(jurisdiction, year_key)
            if is_fallback and year_key not in warned_years:
                warnings.append(
                    f"No tax table for {year_key}; using latest known rates."
                )
                warned_years.add(year_key)

            actual_gross = sum(
                (monthly_gross_by_offset[m] for m in offsets), _ZERO
            )
            base_gross = base_monthly_amount * Decimal(len(offsets))
            actual_it = compute_progressive_tax(actual_gross, bands)
            base_it = compute_progressive_tax(base_gross, bands)
            delta_it = actual_it - base_it
            total_dev = actual_gross - base_gross

            per_month_it = _allocate_year_income_tax(
                offsets=offsets,
                monthly_gross=monthly_gross_by_offset,
                base_monthly=base_monthly_amount,
                base_it=base_it,
                actual_it=actual_it,
                delta_it=delta_it,
                total_dev=total_dev,
                actual_gross=actual_gross,
            )
            for m, it in per_month_it.items():
                _, ni = result[m]
                result[m] = (it, ni)

    # NI: per-month, using that month's gross against monthly thresholds.
    if apply_ni:
        for m, gross in monthly_gross_by_offset.items():
            y, mth = offset_to_year_month(
                profile_start_date.year, profile_start_date.month, m
            )
            ni_bands, is_fallback = get_ni_bands(tax_year_key(y, mth))
            if is_fallback and tax_year_key(y, mth) not in warned_years:
                warnings.append(
                    f"No NI table for {tax_year_key(y, mth)}; using latest "
                    "known rates."
                )
                warned_years.add(tax_year_key(y, mth))
            ni = compute_progressive_tax(gross, ni_bands)
            it, _ = result[m]
            result[m] = (it, ni)

    return result, warnings


def _allocate_year_income_tax(
    *,
    offsets: list[int],
    monthly_gross: dict[int, Decimal],
    base_monthly: Decimal,
    base_it: Decimal,
    actual_it: Decimal,
    delta_it: Decimal,
    total_dev: Decimal,
    actual_gross: Decimal,
) -> dict[int, Decimal]:
    """Allocate annual income tax across months of one tax-year segment.

    Algorithm:
      - Non-override months pay ``base_it / N`` (their baseline share).
      - Override months pay that baseline + their share of ``delta_it``,
        proportional to ``gross − base_monthly``.
      - If deviations cancel (total_dev == 0) or base_it is nonsensical,
        fall back to proportional-to-gross so totals stay consistent.
      - Per-month IT is clamped at zero (a reduction below zero would imply
        a refund for that month, which this planning model doesn't support).
    """
    n = len(offsets)
    out: dict[int, Decimal] = {}
    if n == 0:
        return out

    base_per_month = base_it / Decimal(n)

    if total_dev == 0:
        # No net deviation from the base scenario. Distribute proportional
        # to each month's gross (reduces to even split when all months
        # equal base_monthly).
        for m in offsets:
            if actual_gross > 0:
                out[m] = actual_it * (monthly_gross[m] / actual_gross)
            else:
                out[m] = _ZERO
        return out

    for m in offsets:
        dev = monthly_gross[m] - base_monthly
        it = base_per_month + delta_it * (dev / total_dev)
        out[m] = max(it, _ZERO)
    return out
