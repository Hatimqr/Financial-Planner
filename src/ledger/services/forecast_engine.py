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
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from ledger.services.tax_engine import compute_line_tax

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
class TaxProfileInput:
    """Engine-facing view of a tax profile attached to a line."""

    id: int
    name: str
    jurisdiction: str  # 'scotland' | 'ruk'
    apply_income_tax: bool
    apply_ni: bool


@dataclass
class LineInput:
    """Engine-facing view of a forecast line."""

    id: int
    label: str
    kind: str  # 'inflow' | 'outflow'
    amount: Decimal
    start_month_offset: int
    end_month_offset: int
    tax_profile: TaxProfileInput | None = None


@dataclass
class OverrideInput:
    """Engine-facing view of a line override.

    ``effect_span`` controls how long the override is in force:
      - ``"single_month"`` — applies only to ``month_offset`` (historical).
      - ``"until_next"`` — applies from ``month_offset`` forwards, ending at
        either the next override on the same line or the line's window end.
    """

    line_id: int
    month_offset: int
    amount: Decimal
    effect_span: str = "single_month"


@dataclass
class InvestmentInput:
    """Engine-facing view of an investment holding.

    ``annual_growth_rate`` is stored as a percentage (e.g. ``Decimal('7.0')``
    for 7%). Monthly compounding applies ``(1 + rate/100) ** (1/12)`` to the
    opening balance; contributions are added at month-end and do not grow in
    the month they're deposited (ordinary-annuity convention).
    """

    id: int
    label: str
    starting_balance: Decimal
    monthly_contribution: Decimal
    annual_growth_rate: Decimal  # percentage, e.g. Decimal("7.0") for 7%


@dataclass
class InvestmentOverrideInput:
    """Engine-facing view of an investment monthly-contribution override.

    Same semantics as :class:`OverrideInput`: ``single_month`` replaces the
    contribution at exactly ``month_offset``; ``until_next`` applies from
    ``month_offset`` forwards until another override on the same investment
    or the profile horizon ends.
    """

    investment_id: int
    month_offset: int
    amount: Decimal
    effect_span: str = "single_month"


# Adjuster receives the current amount — that's the override-resolved amount if
# an override applied to this (line, month), otherwise the line's base amount.
# It is NOT always the base amount.
Adjuster = Callable[[LineInput, int, Decimal], Decimal]


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LineMonth:
    """Per-line, per-month contribution detail.

    ``effective_amount`` remains the figure that contributes to the month's
    total_inflow / total_outflow. For a taxed inflow line, that's the NET
    figure (gross − income_tax − ni). For untaxed lines, it equals the base
    amount (or the override / adjusted value when one applies).

    ``gross_amount`` is populated only for lines with an attached tax
    profile; it's the pre-tax figure that went into the tax calculation.
    ``None`` signals "no tax computation happened".
    """

    month_offset: int
    base_amount: Decimal
    effective_amount: Decimal
    is_overridden: bool
    is_adjusted: bool
    gross_amount: Decimal | None = None
    income_tax: Decimal = Decimal("0")
    ni: Decimal = Decimal("0")


@dataclass(frozen=True)
class MonthlyInvestment:
    """Per-investment, per-month state.

    ``closing_balance`` = ``opening_balance * monthly_multiplier + contribution``
    where the multiplier is ``(1 + annual_rate) ** (1/12)`` via Decimal ln/exp.
    ``growth`` is ``opening_balance * (monthly_multiplier - 1)`` — the paper gain
    on the carry-over balance this month. Contribution is ``not`` grown in the
    same month it's deposited.

    ``contribution`` is the effective value after override resolution;
    ``base_contribution`` is the investment's unchanging base amount, kept
    parallel to :attr:`LineMonth.base_amount` so the UI can show the delta.
    """

    investment_id: int
    label: str
    opening_balance: Decimal
    contribution: Decimal
    growth: Decimal
    closing_balance: Decimal
    base_contribution: Decimal = Decimal("0")
    is_overridden: bool = False


@dataclass(frozen=True)
class MonthlyCashflow:
    """One month of the projection.

    ``total_outflow`` INCLUDES investment contributions for this month — the
    contribution is a real cash outflow that drops the cash balance. Investment
    growth lives in ``investment_growth`` and does NOT affect the cashflow math
    (it's a paper gain, not cash).
    """

    month_offset: int
    year_month: str
    opening_balance: Decimal
    total_inflow: Decimal
    total_outflow: Decimal
    net: Decimal
    closing_balance: Decimal
    line_contributions: dict[int, LineMonth]
    is_deficit: bool
    # Investment aggregates for this month. All four fields are always set;
    # zero-valued when the profile has no investments.
    investment_contributions: Decimal
    investment_growth: Decimal
    investment_value: Decimal
    investments: dict[int, MonthlyInvestment]


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
class InvestmentSummary:
    """Per-investment roll-up over the horizon."""

    investment_id: int
    label: str
    starting_balance: Decimal
    total_contributed: Decimal
    total_growth: Decimal
    ending_balance: Decimal
    override_count: int = 0


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
    # Investment aggregates across the horizon. All zero when the profile
    # has no investments.
    investment_summaries: list[InvestmentSummary]
    total_investment_contrib: Decimal
    total_investment_growth: Decimal
    ending_investment_value: Decimal
    # Non-fatal warnings surfaced from the projection (e.g. tax-table
    # fallback to a prior year). UI can render these as yellow banners.
    warnings: list[str] = field(default_factory=list)


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


def _build_override_resolver(
    overrides: Iterable[OverrideInput],
    line_by_id: dict[int, LineInput],
) -> Callable[[int, int], OverrideInput | None]:
    """Build a resolver for effective override at (line_id, month).

    Priority per month:
      1. single_month override at exactly this month
      2. latest until_next override with start_month <= this month
      3. None (caller falls back to line.amount)

    Overrides outside a line's active window are ignored — mirrors the old
    flat-dict filter. The function instantiated once per projection; the
    returned resolver is pure/memoization-friendly.
    """
    by_line: dict[int, dict] = {}
    for o in overrides:
        line = line_by_id.get(o.line_id)
        if line is None:
            continue
        if not (
            line.start_month_offset <= o.month_offset <= line.end_month_offset
        ):
            continue
        entry = by_line.setdefault(
            o.line_id, {"single": {}, "steps": []}
        )
        if o.effect_span == "single_month":
            entry["single"][o.month_offset] = o
        else:  # "until_next"
            entry["steps"].append(o)
    for data in by_line.values():
        data["steps"].sort(key=lambda o: o.month_offset)

    def resolve(line_id: int, month: int) -> OverrideInput | None:
        data = by_line.get(line_id)
        if data is None:
            return None
        single = data["single"].get(month)
        if single is not None:
            return single
        active: OverrideInput | None = None
        for step in data["steps"]:
            if step.month_offset <= month:
                active = step
            else:
                break
        return active

    return resolve


def _build_investment_override_resolver(
    overrides: Iterable[InvestmentOverrideInput],
    horizon_months: int,
) -> Callable[[int, int], InvestmentOverrideInput | None]:
    """Build a resolver for effective override at (investment_id, month).

    Mirrors :func:`_build_override_resolver`. Investments have no per-line
    window, so the only bound is the profile horizon ``[0, horizon-1]``.
    """
    by_inv: dict[int, dict] = {}
    for o in overrides:
        if not (0 <= o.month_offset < horizon_months):
            continue
        entry = by_inv.setdefault(
            o.investment_id, {"single": {}, "steps": []}
        )
        if o.effect_span == "single_month":
            entry["single"][o.month_offset] = o
        else:  # "until_next"
            entry["steps"].append(o)
    for data in by_inv.values():
        data["steps"].sort(key=lambda o: o.month_offset)

    def resolve(investment_id: int, month: int) -> InvestmentOverrideInput | None:
        data = by_inv.get(investment_id)
        if data is None:
            return None
        single = data["single"].get(month)
        if single is not None:
            return single
        active: InvestmentOverrideInput | None = None
        for step in data["steps"]:
            if step.month_offset <= month:
                active = step
            else:
                break
        return active

    return resolve


def _monthly_multiplier(annual_rate_pct: Decimal) -> Decimal:
    """Convert an annual growth rate (as %) to its equivalent monthly multiplier.

    Uses Decimal ``ln`` + ``exp`` to avoid float round-trips. ``rate=0`` short-
    circuits to exactly ``Decimal(1)`` to keep the no-growth case numerically
    clean. Engine keeps full precision; 2dp quantization happens at the
    display/export boundary per the rounding policy in spec §7.2.
    """
    annual_frac = annual_rate_pct / Decimal(100)
    if annual_frac == 0:
        return Decimal(1)
    return ((Decimal(1) + annual_frac).ln() / Decimal(12)).exp()


def project(
    profile: ProfileInput,
    lines: Iterable[LineInput],
    overrides: Iterable[OverrideInput] = (),
    investments: Iterable[InvestmentInput] = (),
    investment_overrides: Iterable[InvestmentOverrideInput] = (),
    *,
    adjuster: Adjuster | None = None,
) -> CashflowProjection:
    """Compute the month-by-month cashflow projection for a profile.

    Args:
        profile: The profile's opening balance, horizon, and anchor date.
        lines: Iterable of lines defining recurring monthly cash deltas.
        overrides: Optional per-(line, month) absolute-amount replacements.
        investments: Optional iterable of investments. Each contributes
            ``monthly_contribution`` to the cashflow's total_outflow every month
            (cash actually leaves), and compounds its balance by its monthly
            multiplier. Growth is reported but does NOT affect the cashflow.
        investment_overrides: Optional per-(investment, month) contribution
            replacements. Same semantics as line overrides.
        adjuster: Optional pure callable ``(line, month_offset, current_amount)
            -> adjusted_amount`` applied after override resolution. Defaults to
            an identity. Use for what-if scenarios (tax, inflation, FX shocks).

    Returns:
        A :class:`CashflowProjection` with per-month detail and summary stats.
    """
    lines_list = list(lines)
    investments_list = list(investments)
    line_by_id = {line.id: line for line in lines_list}
    resolve_override = _build_override_resolver(overrides, line_by_id)
    resolve_inv_override = _build_investment_override_resolver(
        investment_overrides, profile.horizon_months
    )

    line_totals: dict[int, Decimal] = {line.id: Decimal("0") for line in lines_list}
    line_active: dict[int, int] = {line.id: 0 for line in lines_list}
    line_ovr_count: dict[int, int] = {line.id: 0 for line in lines_list}

    # Tax pre-pass: for each line with an attached tax profile, resolve the
    # post-override / post-adjuster gross across its active window, then
    # compute (income_tax, ni) per month. Stored as a lookup so the
    # month-loop can subtract it without re-aggregating.
    line_tax_by_month: dict[tuple[int, int], tuple[Decimal, Decimal]] = {}
    projection_warnings: list[str] = []
    for line in lines_list:
        if line.tax_profile is None:
            continue
        gross_by_offset: dict[int, Decimal] = {}
        for m in range(profile.horizon_months):
            if not (line.start_month_offset <= m <= line.end_month_offset):
                continue
            resolved = resolve_override(line.id, m)
            amount = resolved.amount if resolved is not None else line.amount
            if adjuster is not None:
                amount = adjuster(line, m, amount)
            gross_by_offset[m] = amount
        per_month, warns = compute_line_tax(
            profile_start_date=profile.start_date,
            monthly_gross_by_offset=gross_by_offset,
            base_monthly_amount=line.amount,
            jurisdiction=line.tax_profile.jurisdiction,
            apply_income_tax=line.tax_profile.apply_income_tax,
            apply_ni=line.tax_profile.apply_ni,
        )
        for off, (it, ni) in per_month.items():
            line_tax_by_month[(line.id, off)] = (it, ni)
        for w in warns:
            if w not in projection_warnings:
                projection_warnings.append(w)

    # Precompute per-investment monthly multipliers and rolling balances.
    inv_multipliers: dict[int, Decimal] = {
        inv.id: _monthly_multiplier(inv.annual_growth_rate)
        for inv in investments_list
    }
    inv_opening: dict[int, Decimal] = {
        inv.id: inv.starting_balance for inv in investments_list
    }
    inv_total_contrib: dict[int, Decimal] = {
        inv.id: Decimal("0") for inv in investments_list
    }
    inv_total_growth: dict[int, Decimal] = {
        inv.id: Decimal("0") for inv in investments_list
    }
    inv_ovr_count: dict[int, int] = {
        inv.id: 0 for inv in investments_list
    }

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
            resolved = resolve_override(line.id, m)
            if resolved is not None:
                current = resolved.amount
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

            # Tax subtraction (taxed inflow lines only). The tax pre-pass
            # already ran the same override + adjuster resolution, so the
            # gross here is what the tax calc saw.
            tax_key = (line.id, m)
            if tax_key in line_tax_by_month:
                it, ni = line_tax_by_month[tax_key]
                gross_for_line: Decimal | None = current
                effective = current - it - ni
            else:
                it = Decimal("0")
                ni = Decimal("0")
                gross_for_line = None
                effective = current

            contributions[line.id] = LineMonth(
                month_offset=m,
                base_amount=base,
                effective_amount=effective,
                is_overridden=is_overridden,
                is_adjusted=is_adjusted,
                gross_amount=gross_for_line,
                income_tax=it,
                ni=ni,
            )

            signed = effective if line.kind == "inflow" else -effective
            line_totals[line.id] += signed
            line_active[line.id] += 1

            if line.kind == "inflow":
                inflow += effective
            else:
                outflow += effective

        # Investment math: compound each investment's opening balance, add its
        # contribution at month-end, accumulate aggregates. Overrides replace
        # the base monthly_contribution on a per-month basis.
        inv_month_state: dict[int, MonthlyInvestment] = {}
        inv_total_contrib_month = Decimal("0")
        inv_total_growth_month = Decimal("0")
        inv_total_value_month = Decimal("0")
        for inv in investments_list:
            opening_inv = inv_opening[inv.id]
            growth = opening_inv * (inv_multipliers[inv.id] - Decimal(1))

            resolved_inv = resolve_inv_override(inv.id, m)
            if resolved_inv is not None:
                contribution = resolved_inv.amount
                is_inv_overridden = True
                inv_ovr_count[inv.id] += 1
            else:
                contribution = inv.monthly_contribution
                is_inv_overridden = False

            closing_inv = opening_inv + growth + contribution

            inv_month_state[inv.id] = MonthlyInvestment(
                investment_id=inv.id,
                label=inv.label,
                opening_balance=opening_inv,
                contribution=contribution,
                growth=growth,
                closing_balance=closing_inv,
                base_contribution=inv.monthly_contribution,
                is_overridden=is_inv_overridden,
            )
            inv_total_contrib_month += contribution
            inv_total_growth_month += growth
            inv_total_value_month += closing_inv
            inv_total_contrib[inv.id] += contribution
            inv_total_growth[inv.id] += growth
            inv_opening[inv.id] = closing_inv

        # Investment contributions are real cash outflows.
        outflow += inv_total_contrib_month

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
                investment_contributions=inv_total_contrib_month,
                investment_growth=inv_total_growth_month,
                investment_value=inv_total_value_month,
                investments=inv_month_state,
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

    investment_summaries = [
        InvestmentSummary(
            investment_id=inv.id,
            label=inv.label,
            starting_balance=inv.starting_balance,
            total_contributed=inv_total_contrib[inv.id],
            total_growth=inv_total_growth[inv.id],
            # inv_opening holds the rolling balance; after the loop that's the
            # final closing balance.
            ending_balance=inv_opening[inv.id],
            override_count=inv_ovr_count[inv.id],
        )
        for inv in investments_list
    ]
    total_inv_contrib = sum(
        (s.total_contributed for s in investment_summaries), Decimal("0")
    )
    total_inv_growth = sum(
        (s.total_growth for s in investment_summaries), Decimal("0")
    )
    ending_inv_value = sum(
        (s.ending_balance for s in investment_summaries), Decimal("0")
    )

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
        investment_summaries=investment_summaries,
        total_investment_contrib=total_inv_contrib,
        total_investment_growth=total_inv_growth,
        ending_investment_value=ending_inv_value,
        warnings=projection_warnings,
    )
