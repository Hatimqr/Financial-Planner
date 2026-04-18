"""Pure-function projection engine for the forecasting module.

Converts a profile's inputs (opening balance, horizon, lines, overrides) into a
month-by-month cashflow curve. Zero coupling to the database layer: the engine
consumes plain input dataclasses, not ORM objects. The service layer
(Iteration 3) converts ORM rows into these inputs before calling ``project()``.

The engine is intentionally small and disposable (see ``docs/future-features.md``
§10). When derived-line types (tax, percent-of-income, interest) arrive, this
module is expected to be rewritten around a dependency graph, not extended in
place. The input and output dataclasses are likely to survive that transition;
the ``project()`` internals are not.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

# ---------------------------------------------------------------------------
# Input dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ProfileInput:
    """Engine-facing view of a forecast profile."""

    id: int
    opening_balance: Decimal
    horizon_months: int
    start_date: date


@dataclass
class LineInput:
    """Engine-facing view of a forecast line."""

    id: int
    label: str
    kind: str  # 'inflow' | 'outflow'
    amount: Decimal
    start_month_offset: int
    end_month_offset: int


@dataclass
class OverrideInput:
    """Engine-facing view of a per-month line override."""

    line_id: int
    month_offset: int
    amount: Decimal


# Adjuster receives the current amount — that's the override-resolved amount if
# an override applied to this (line, month), otherwise the line's base amount.
# It is NOT always the base amount.
Adjuster = Callable[[LineInput, int, Decimal], Decimal]


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LineMonth:
    """Per-line, per-month contribution detail."""

    month_offset: int
    base_amount: Decimal
    effective_amount: Decimal
    is_overridden: bool
    is_adjusted: bool


@dataclass(frozen=True)
class MonthlyCashflow:
    """One month of the projection."""

    month_offset: int
    year_month: str
    opening_balance: Decimal
    total_inflow: Decimal
    total_outflow: Decimal
    net: Decimal
    closing_balance: Decimal
    line_contributions: dict[int, LineMonth]
    is_deficit: bool


@dataclass(frozen=True)
class LineSummary:
    """Per-line roll-up over the horizon."""

    line_id: int
    label: str
    kind: str
    total_contribution: Decimal  # signed: +inflow, -outflow
    active_months: int
    override_count: int


@dataclass(frozen=True)
class CashflowProjection:
    """Full projection result for one profile."""

    profile_id: int
    months: list[MonthlyCashflow]
    line_summaries: list[LineSummary]
    total_inflow: Decimal
    total_outflow: Decimal
    net: Decimal
    ending_balance: Decimal
    deficit_months: int
    min_balance: Decimal
    min_balance_month: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ym(start_date: date, month_offset: int) -> str:
    """Return "YYYY-MM" for ``month_offset`` months after ``start_date``."""
    total_months = start_date.month - 1 + month_offset
    year = start_date.year + total_months // 12
    month = total_months % 12 + 1
    return f"{year:04d}-{month:02d}"


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


def project(
    profile: ProfileInput,
    lines: Iterable[LineInput],
    overrides: Iterable[OverrideInput] = (),
    *,
    adjuster: Adjuster | None = None,
) -> CashflowProjection:
    """Compute the month-by-month cashflow projection for a profile.

    Args:
        profile: The profile's opening balance, horizon, and anchor date.
        lines: Iterable of lines defining recurring monthly cash deltas.
        overrides: Optional per-(line, month) absolute-amount replacements.
        adjuster: Optional pure callable ``(line, month_offset, current_amount)
            -> adjusted_amount`` applied after override resolution. Defaults to
            an identity. Use for what-if scenarios (tax, inflation, FX shocks).

    Returns:
        A :class:`CashflowProjection` with per-month detail and summary stats.
    """
    lines_list = list(lines)
    line_by_id = {line.id: line for line in lines_list}
    override_lookup = {
        (o.line_id, o.month_offset): o.amount
        for o in overrides
        if o.line_id in line_by_id
        and line_by_id[o.line_id].start_month_offset
        <= o.month_offset
        <= line_by_id[o.line_id].end_month_offset
    }

    line_totals: dict[int, Decimal] = {line.id: Decimal("0") for line in lines_list}
    line_active: dict[int, int] = {line.id: 0 for line in lines_list}
    line_ovr_count: dict[int, int] = {line.id: 0 for line in lines_list}

    months: list[MonthlyCashflow] = []
    opening = profile.opening_balance
    # min_balance tracks the minimum *closing* balance across the horizon.
    # For a zero-horizon profile, we fall back to opening_balance after the loop.
    min_balance: Decimal | None = None
    min_month = 0
    deficit_months = 0

    for m in range(profile.horizon_months):
        contributions: dict[int, LineMonth] = {}
        inflow = Decimal("0")
        outflow = Decimal("0")

        for line in lines_list:
            if not (line.start_month_offset <= m <= line.end_month_offset):
                continue

            base = line.amount
            key = (line.id, m)
            if key in override_lookup:
                current = override_lookup[key]
                is_overridden = True
                line_ovr_count[line.id] += 1
            else:
                current = base
                is_overridden = False

            is_adjusted = False
            if adjuster is not None:
                adjusted_value = adjuster(line, m, current)
                if adjusted_value != current:
                    current = adjusted_value
                    is_adjusted = True

            effective = current
            contributions[line.id] = LineMonth(
                month_offset=m,
                base_amount=base,
                effective_amount=effective,
                is_overridden=is_overridden,
                is_adjusted=is_adjusted,
            )

            signed = effective if line.kind == "inflow" else -effective
            line_totals[line.id] += signed
            line_active[line.id] += 1

            if line.kind == "inflow":
                inflow += effective
            else:
                outflow += effective

        net = inflow - outflow
        closing = opening + net
        if min_balance is None or closing < min_balance:
            min_balance = closing
            min_month = m
        if closing < 0:
            deficit_months += 1

        months.append(
            MonthlyCashflow(
                month_offset=m,
                year_month=_ym(profile.start_date, m),
                opening_balance=opening,
                total_inflow=inflow,
                total_outflow=outflow,
                net=net,
                closing_balance=closing,
                line_contributions=contributions,
                is_deficit=closing < 0,
            )
        )
        opening = closing

    ending_balance = months[-1].closing_balance if months else profile.opening_balance
    total_inflow = sum((mc.total_inflow for mc in months), Decimal("0"))
    total_outflow = sum((mc.total_outflow for mc in months), Decimal("0"))

    # Zero-horizon fallback: no closings were recorded, so anchor min to opening.
    if min_balance is None:
        min_balance = profile.opening_balance
        min_month = 0

    line_summaries = [
        LineSummary(
            line_id=line.id,
            label=line.label,
            kind=line.kind,
            total_contribution=line_totals[line.id],
            active_months=line_active[line.id],
            override_count=line_ovr_count[line.id],
        )
        for line in lines_list
    ]

    return CashflowProjection(
        profile_id=profile.id,
        months=months,
        line_summaries=line_summaries,
        total_inflow=total_inflow,
        total_outflow=total_outflow,
        net=total_inflow - total_outflow,
        ending_balance=ending_balance,
        deficit_months=deficit_months,
        min_balance=min_balance,
        min_balance_month=min_month,
    )
