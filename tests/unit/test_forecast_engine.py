"""Tests for the pure-function projection engine.

No DB fixtures — the engine consumes plain input dataclasses. Tests construct
scenarios directly and assert exact Decimal equality on outputs.
"""

from datetime import date
from decimal import Decimal

from ledger.services.forecast_engine import (
    InvestmentInput,
    InvestmentOverrideInput,
    LineInput,
    OverrideInput,
    ProfileInput,
    TaxProfileInput,
    project,
)

# ---------------------------------------------------------------------------
# Fixtures (plain builder helpers, not pytest fixtures)
# ---------------------------------------------------------------------------


def make_profile(
    *,
    opening: str = "0",
    horizon: int = 7,
    start: date = date(2026, 6, 1),
    profile_id: int = 1,
) -> ProfileInput:
    return ProfileInput(
        id=profile_id,
        opening_balance=Decimal(opening),
        horizon_months=horizon,
        start_date=start,
    )


def make_line(
    line_id: int,
    label: str,
    kind: str,
    amount: str,
    start: int = 0,
    end: int = 6,
) -> LineInput:
    return LineInput(
        id=line_id,
        label=label,
        kind=kind,
        amount=Decimal(amount),
        start_month_offset=start,
        end_month_offset=end,
    )


def make_override(line_id: int, month_offset: int, amount: str) -> OverrideInput:
    return OverrideInput(
        line_id=line_id, month_offset=month_offset, amount=Decimal(amount)
    )


def make_investment(
    inv_id: int,
    label: str,
    starting: str = "0",
    contribution: str = "0",
    rate_pct: str = "0",
) -> InvestmentInput:
    return InvestmentInput(
        id=inv_id,
        label=label,
        starting_balance=Decimal(starting),
        monthly_contribution=Decimal(contribution),
        annual_growth_rate=Decimal(rate_pct),
    )


# ---------------------------------------------------------------------------
# Base cases (spec §7.3, adapted to the enriched output)
# ---------------------------------------------------------------------------


class TestBaseCases:
    def test_empty_profile_flat_balance(self):
        """Empty profile — every month nets 0, balance flat at opening."""
        profile = make_profile(opening="1000", horizon=7)
        proj = project(profile, [])

        assert len(proj.months) == 7
        assert all(m.net == Decimal("0") for m in proj.months)
        assert all(m.closing_balance == Decimal("1000") for m in proj.months)
        assert proj.line_summaries == []
        assert proj.min_balance == Decimal("1000")
        assert proj.min_balance_month == 0
        assert proj.ending_balance == Decimal("1000")
        assert proj.deficit_months == 0

    def test_one_inflow_full_horizon(self):
        """Linear growth with a single inflow over the full horizon."""
        profile = make_profile(opening="0", horizon=7)
        salary = make_line(1, "Salary", "inflow", "10000", 0, 6)
        proj = project(profile, [salary])

        assert proj.months[0].closing_balance == Decimal("10000")
        assert proj.months[6].closing_balance == Decimal("70000")
        assert proj.ending_balance == Decimal("70000")
        assert proj.total_inflow == Decimal("70000")
        assert proj.total_outflow == Decimal("0")

        summary = proj.line_summaries[0]
        assert summary.total_contribution == Decimal("70000")
        assert summary.active_months == 7
        assert summary.override_count == 0

        for m in proj.months:
            assert m.line_contributions[1].is_overridden is False
            assert m.line_contributions[1].is_adjusted is False

    def test_one_outflow_partial_window(self):
        """Outflow contributes only in its window."""
        profile = make_profile(opening="10000", horizon=7)
        rent = make_line(1, "Rent", "outflow", "4000", start=2, end=4)
        proj = project(profile, [rent])

        # Months 0, 1, 5, 6 untouched
        assert proj.months[0].closing_balance == Decimal("10000")
        assert proj.months[1].closing_balance == Decimal("10000")
        # Months 2-4 each drop 4000
        assert proj.months[2].closing_balance == Decimal("6000")
        assert proj.months[3].closing_balance == Decimal("2000")
        assert proj.months[4].closing_balance == Decimal("-2000")
        # Months 5, 6 flat
        assert proj.months[5].closing_balance == Decimal("-2000")
        assert proj.months[6].closing_balance == Decimal("-2000")

        summary = proj.line_summaries[0]
        assert summary.active_months == 3
        assert summary.total_contribution == Decimal("-12000")

    def test_overlapping_lines_additive(self):
        """Multiple lines with different windows sum correctly."""
        profile = make_profile(opening="0", horizon=4)
        salary = make_line(1, "Salary", "inflow", "5000", 0, 3)
        rent = make_line(2, "Rent", "outflow", "2000", 0, 3)
        bonus = make_line(3, "Bonus", "inflow", "1000", 2, 2)
        proj = project(profile, [salary, rent, bonus])

        # Month 0, 1: 5000 - 2000 = 3000
        # Month 2: 5000 + 1000 - 2000 = 4000
        # Month 3: 5000 - 2000 = 3000
        assert proj.months[0].net == Decimal("3000")
        assert proj.months[1].net == Decimal("3000")
        assert proj.months[2].net == Decimal("4000")
        assert proj.months[3].net == Decimal("3000")
        assert proj.ending_balance == Decimal("13000")

    def test_deficit_months_counted(self):
        """deficit_months counts months with closing < 0."""
        profile = make_profile(opening="1000", horizon=5)
        rent = make_line(1, "Rent", "outflow", "600", 0, 4)
        proj = project(profile, [rent])

        # Closings: 400 (m0), -200 (m1), -800 (m2), -1400 (m3), -2000 (m4)
        # Deficits at months 1, 2, 3, 4 → 4 months
        assert proj.deficit_months == 4
        assert [m.is_deficit for m in proj.months] == [False, True, True, True, True]

    def test_single_month_horizon(self):
        """horizon_months == 1 returns exactly one MonthlyCashflow."""
        profile = make_profile(opening="500", horizon=1)
        salary = make_line(1, "Salary", "inflow", "100", 0, 0)
        proj = project(profile, [salary])

        assert len(proj.months) == 1
        assert proj.months[0].closing_balance == Decimal("600")
        assert proj.ending_balance == Decimal("600")

    def test_zero_amount_line(self):
        """A zero-amount line is included but contributes nothing."""
        profile = make_profile(opening="1000", horizon=3)
        zero = make_line(1, "Placeholder", "outflow", "0", 0, 2)
        proj = project(profile, [zero])

        assert all(m.closing_balance == Decimal("1000") for m in proj.months)
        assert proj.min_balance == Decimal("1000")
        assert proj.deficit_months == 0
        summary = proj.line_summaries[0]
        assert summary.total_contribution == Decimal("0")
        assert summary.active_months == 3

    def test_one_off_line(self):
        """start == end contributes in exactly one month."""
        profile = make_profile(opening="0", horizon=5)
        flight = make_line(1, "Flight", "outflow", "2500", 3, 3)
        proj = project(profile, [flight])

        # Only month 3 moves
        assert proj.months[0].net == Decimal("0")
        assert proj.months[2].net == Decimal("0")
        assert proj.months[3].net == Decimal("-2500")
        assert proj.months[4].net == Decimal("0")

        summary = proj.line_summaries[0]
        assert summary.active_months == 1
        assert summary.total_contribution == Decimal("-2500")

    def test_min_balance_tracks_dip(self):
        """A dip in month 3 with recovery reports min_balance_month == 3."""
        profile = make_profile(opening="0", horizon=6)
        salary = make_line(1, "Salary", "inflow", "1000", 0, 5)
        big_expense = make_line(2, "Car", "outflow", "5000", 3, 3)
        proj = project(profile, [salary, big_expense])

        # Balances: 1000, 2000, 3000, -1000 (dip), 0, 1000
        assert proj.months[3].closing_balance == Decimal("-1000")
        assert proj.min_balance == Decimal("-1000")
        assert proj.min_balance_month == 3


# ---------------------------------------------------------------------------
# Override cases
# ---------------------------------------------------------------------------


class TestOverrides:
    def test_override_replaces_base(self):
        """One override on month 2 — that month uses override, others base."""
        profile = make_profile(opening="0", horizon=5)
        rent = make_line(1, "Rent", "outflow", "1000", 0, 4)
        ovr = make_override(line_id=1, month_offset=2, amount="1500")
        proj = project(profile, [rent], [ovr])

        for m in range(5):
            cell = proj.months[m].line_contributions[1]
            if m == 2:
                assert cell.is_overridden is True
                assert cell.is_adjusted is False
                assert cell.effective_amount == Decimal("1500")
            else:
                assert cell.is_overridden is False
                assert cell.is_adjusted is False
                assert cell.effective_amount == Decimal("1000")

        assert proj.line_summaries[0].override_count == 1
        # Total outflow: 4*1000 + 1*1500 = 5500
        assert proj.total_outflow == Decimal("5500")

    def test_zero_override_skips_month(self):
        """Override amount=0 makes the line contribute nothing that month."""
        profile = make_profile(opening="0", horizon=3)
        rent = make_line(1, "Rent", "outflow", "1000", 0, 2)
        ovr = make_override(line_id=1, month_offset=1, amount="0")
        proj = project(profile, [rent], [ovr])

        assert proj.months[0].total_outflow == Decimal("1000")
        assert proj.months[1].total_outflow == Decimal("0")
        assert proj.months[2].total_outflow == Decimal("1000")

        cell = proj.months[1].line_contributions[1]
        assert cell.is_overridden is True
        assert cell.effective_amount == Decimal("0")
        assert proj.line_summaries[0].override_count == 1

    def test_multiple_overrides_one_line(self):
        """Each override applies only to its month; order-independent."""
        profile = make_profile(opening="0", horizon=5)
        rent = make_line(1, "Rent", "outflow", "1000", 0, 4)
        overrides = [
            make_override(1, 3, "1300"),
            make_override(1, 1, "1100"),  # out of order intentionally
        ]
        proj = project(profile, [rent], overrides)

        assert proj.months[0].line_contributions[1].effective_amount == Decimal("1000")
        assert proj.months[1].line_contributions[1].effective_amount == Decimal("1100")
        assert proj.months[2].line_contributions[1].effective_amount == Decimal("1000")
        assert proj.months[3].line_contributions[1].effective_amount == Decimal("1300")
        assert proj.months[4].line_contributions[1].effective_amount == Decimal("1000")
        assert proj.line_summaries[0].override_count == 2

    def test_override_outside_window_ignored(self):
        """Override whose month offset is outside parent window is silently ignored."""
        profile = make_profile(opening="0", horizon=5)
        rent = make_line(1, "Rent", "outflow", "1000", 1, 3)
        # Override at month 0 (before window) and month 4 (after window)
        overrides = [
            make_override(1, 0, "9999"),
            make_override(1, 4, "9999"),
        ]
        proj = project(profile, [rent], overrides)

        # Month 0 and 4 out of window → line contributes nothing
        assert proj.months[0].total_outflow == Decimal("0")
        assert proj.months[4].total_outflow == Decimal("0")
        # Months 1-3 use base amount (overrides were ignored, base applies)
        assert proj.months[1].total_outflow == Decimal("1000")
        assert proj.months[2].total_outflow == Decimal("1000")
        assert proj.months[3].total_outflow == Decimal("1000")
        # No overrides actually applied
        assert proj.line_summaries[0].override_count == 0

    def test_override_unknown_line_id_ignored(self):
        """Override referencing a line_id not in lines is silently ignored."""
        profile = make_profile(opening="0", horizon=3)
        rent = make_line(1, "Rent", "outflow", "1000", 0, 2)
        stale = make_override(line_id=999, month_offset=1, amount="5555")
        proj = project(profile, [rent], [stale])

        assert proj.total_outflow == Decimal("3000")
        assert proj.line_summaries[0].override_count == 0


# ---------------------------------------------------------------------------
# Adjuster cases
# ---------------------------------------------------------------------------


class TestAdjuster:
    def test_default_identity(self):
        """No adjuster produces same result as identity adjuster."""
        profile = make_profile(opening="0", horizon=3)
        salary = make_line(1, "Salary", "inflow", "1000", 0, 2)

        default_proj = project(profile, [salary])
        identity_proj = project(profile, [salary], adjuster=lambda _line, _m, a: a)

        assert default_proj.ending_balance == identity_proj.ending_balance
        for m in range(3):
            assert (
                default_proj.months[m].line_contributions[1].is_adjusted
                == identity_proj.months[m].line_contributions[1].is_adjusted
                is False
            )

    def test_flat_tax_on_inflows(self):
        """Adjuster multiplying inflows by 0.80; outflows untouched."""
        profile = make_profile(opening="0", horizon=3)
        salary = make_line(1, "Salary", "inflow", "1000", 0, 2)
        rent = make_line(2, "Rent", "outflow", "300", 0, 2)

        def tax_inflows(line, m, current):
            if line.kind == "inflow":
                return current * Decimal("0.80")
            return current

        proj = project(profile, [salary, rent], adjuster=tax_inflows)

        for m in range(3):
            salary_cell = proj.months[m].line_contributions[1]
            rent_cell = proj.months[m].line_contributions[2]
            assert salary_cell.is_adjusted is True
            assert salary_cell.effective_amount == Decimal("800.00")
            assert rent_cell.is_adjusted is False
            assert rent_cell.effective_amount == Decimal("300")

        # Monthly net = 800 - 300 = 500; over 3 months = 1500
        assert proj.ending_balance == Decimal("1500.00")

    def test_conditional_inflation_shock(self):
        """Adjuster raises outflows 15% starting month 4."""
        profile = make_profile(opening="10000", horizon=6)
        rent = make_line(1, "Rent", "outflow", "1000", 0, 5)

        def shock(line, m, current):
            if m >= 4 and line.kind == "outflow":
                return current * Decimal("1.15")
            return current

        proj = project(profile, [rent], adjuster=shock)

        for m in range(6):
            cell = proj.months[m].line_contributions[1]
            if m < 4:
                assert cell.is_adjusted is False
                assert cell.effective_amount == Decimal("1000")
            else:
                assert cell.is_adjusted is True
                assert cell.effective_amount == Decimal("1150.00")

    def test_adjuster_composes_with_override(self):
        """Override + adjuster both apply; both flags True, values chained."""
        profile = make_profile(opening="0", horizon=3)
        salary = make_line(1, "Salary", "inflow", "1000", 0, 2)
        ovr = make_override(1, 1, "2000")  # month 1 override to 2000

        # Adjuster halves the current amount
        proj = project(profile, [salary], [ovr], adjuster=lambda _line, _m, a: a / Decimal("2"))

        # Month 0: base 1000 → adjuster → 500
        cell0 = proj.months[0].line_contributions[1]
        assert cell0.is_overridden is False
        assert cell0.is_adjusted is True
        assert cell0.effective_amount == Decimal("500")

        # Month 1: override 2000 → adjuster → 1000. Both flags True.
        cell1 = proj.months[1].line_contributions[1]
        assert cell1.is_overridden is True
        assert cell1.is_adjusted is True
        assert cell1.effective_amount == Decimal("1000")

        # Month 2: base → 500
        cell2 = proj.months[2].line_contributions[1]
        assert cell2.is_overridden is False
        assert cell2.is_adjusted is True
        assert cell2.effective_amount == Decimal("500")

    def test_noop_adjuster_not_marked_adjusted(self):
        """Adjuster returning the same value leaves is_adjusted False."""
        profile = make_profile(opening="0", horizon=3)
        salary = make_line(1, "Salary", "inflow", "1000", 0, 2)

        def noop(line, m, current):
            return current

        proj = project(profile, [salary], adjuster=noop)

        for m in range(3):
            cell = proj.months[m].line_contributions[1]
            assert cell.is_adjusted is False


# ---------------------------------------------------------------------------
# Zero-horizon edge case
# ---------------------------------------------------------------------------


class TestZeroHorizon:
    def test_empty_months_well_defined(self):
        """horizon_months == 0 returns a well-formed empty projection."""
        profile = make_profile(opening="5000", horizon=0)
        salary = make_line(1, "Salary", "inflow", "1000", 0, 0)
        proj = project(profile, [salary])

        assert proj.months == []
        assert proj.ending_balance == Decimal("5000")
        assert proj.min_balance == Decimal("5000")
        assert proj.min_balance_month == 0
        assert proj.total_inflow == Decimal("0")
        assert proj.total_outflow == Decimal("0")
        assert proj.net == Decimal("0")
        assert proj.deficit_months == 0
        # Line summary present with zeros
        assert len(proj.line_summaries) == 1
        assert proj.line_summaries[0].total_contribution == Decimal("0")
        assert proj.line_summaries[0].active_months == 0
        assert proj.line_summaries[0].override_count == 0


# ---------------------------------------------------------------------------
# Integration sanity: NYUAD fixture
# ---------------------------------------------------------------------------


class TestNYUADScenario:
    def test_nyuad_ra_with_august_bonus(self):
        """Realistic scenario: NYUAD research assistantship with a bonus override.

        Setup:
          - Opening balance: 5,000 AED
          - Horizon: 7 months (Jun 2026 - Dec 2026)
          - Salary: 10,000 AED inflow, months 0-6
          - Rent: 4,000 AED outflow, months 0-6
          - Groceries: 800 AED outflow, months 0-6
          - August bonus override (month 2): salary raised to 13,000

        Expected:
          Base monthly net (no override):  10,000 - 4,000 - 800 = 5,200
          Override contributes (month 2):  (13,000 - 10,000)    = +3,000
          Total net over 7 months:         7 * 5,200 + 3,000    = 39,400
          ending_balance = 5,000 + 39,400                       = 44,400
        """
        profile = make_profile(opening="5000", horizon=7, start=date(2026, 6, 1))
        salary = make_line(1, "Salary", "inflow", "10000", 0, 6)
        rent = make_line(2, "Rent", "outflow", "4000", 0, 6)
        groceries = make_line(3, "Groceries", "outflow", "800", 0, 6)
        august_bonus = make_override(line_id=1, month_offset=2, amount="13000")

        proj = project(profile, [salary, rent, groceries], [august_bonus])

        assert proj.ending_balance == Decimal("44400")
        assert proj.total_inflow == Decimal("73000")  # 6*10000 + 13000
        assert proj.total_outflow == Decimal("33600")  # 7*(4000+800)
        assert proj.net == Decimal("39400")
        assert proj.deficit_months == 0
        assert proj.min_balance == Decimal("10200")  # month 0 closing: 5000 + 5200
        assert proj.min_balance_month == 0

        # Month labels align with AED start date
        assert proj.months[0].year_month == "2026-06"
        assert proj.months[6].year_month == "2026-12"

        # Override provenance visible
        aug_cell = proj.months[2].line_contributions[1]
        assert aug_cell.is_overridden is True
        assert aug_cell.effective_amount == Decimal("13000")

        # Line summaries
        salary_sum = proj.line_summaries[0]
        assert salary_sum.total_contribution == Decimal("73000")
        assert salary_sum.active_months == 7
        assert salary_sum.override_count == 1

        rent_sum = proj.line_summaries[1]
        assert rent_sum.total_contribution == Decimal("-28000")  # -7 * 4000


# ---------------------------------------------------------------------------
# _ym helper (private but worth smoke-checking month arithmetic)
# ---------------------------------------------------------------------------


class TestYearMonthFormatting:
    def test_year_month_rolls_over(self):
        """Month offsets cross year boundaries correctly."""
        from ledger.services.forecast_engine import _ym

        start = date(2026, 11, 1)
        assert _ym(start, 0) == "2026-11"
        assert _ym(start, 1) == "2026-12"
        assert _ym(start, 2) == "2027-01"
        assert _ym(start, 14) == "2028-01"


# ---------------------------------------------------------------------------
# Investments (Iter 8)
# ---------------------------------------------------------------------------


class TestInvestments:
    def test_zero_growth_single_investment(self):
        """0% growth: each month's contribution stacks linearly."""
        profile = make_profile(opening="0", horizon=7)
        inv = make_investment(1, "Cash", starting="1000", contribution="100", rate_pct="0")
        proj = project(profile, [], (), [inv])

        # Each month: growth = 0, contribution = 100.
        # Closing balance: 1000 + (m+1) * 100  (ordinary-annuity convention)
        for m, mc in enumerate(proj.months):
            assert mc.investments[1].growth == Decimal("0")
            assert mc.investments[1].contribution == Decimal("100")
            assert mc.investments[1].closing_balance == Decimal(1000 + (m + 1) * 100)
            assert mc.investment_contributions == Decimal("100")
            assert mc.investment_growth == Decimal("0")
            assert mc.investment_value == Decimal(1000 + (m + 1) * 100)

        # Horizon summary
        assert len(proj.investment_summaries) == 1
        summary = proj.investment_summaries[0]
        assert summary.total_contributed == Decimal("700")  # 7 * 100
        assert summary.total_growth == Decimal("0")
        assert summary.ending_balance == Decimal("1700")
        assert proj.total_investment_contrib == Decimal("700")
        assert proj.ending_investment_value == Decimal("1700")

    def test_compounding_equivalence(self):
        """12 monthly compounds @ (1+r)^(1/12) equal one annual compound @ 1+r."""
        profile = make_profile(opening="0", horizon=12)
        inv = make_investment(
            1, "Index", starting="1000", contribution="0", rate_pct="12"
        )
        proj = project(profile, [], (), [inv])

        # Residual digits from Decimal.ln/exp round-trip — quantize to 2dp.
        inv_closing = proj.months[11].investments[1].closing_balance
        assert inv_closing.quantize(Decimal("0.01")) == Decimal("1120.00")
        # Summary should agree
        summary = proj.investment_summaries[0]
        assert summary.ending_balance.quantize(Decimal("0.01")) == Decimal("1120.00")
        assert summary.total_growth.quantize(Decimal("0.01")) == Decimal("120.00")

    def test_multi_investment_aggregation(self):
        """Two investments with different rates — aggregates sum independently."""
        profile = make_profile(opening="0", horizon=12)
        a = make_investment(1, "A", starting="1000", contribution="0", rate_pct="12")
        b = make_investment(2, "B", starting="2000", contribution="0", rate_pct="6")
        proj = project(profile, [], (), [a, b])

        # After 12 months: A -> 1120, B -> 2120, sum = 3240.
        closing_a = proj.months[11].investments[1].closing_balance
        closing_b = proj.months[11].investments[2].closing_balance
        assert (closing_a + closing_b).quantize(Decimal("0.01")) == Decimal("3240.00")
        agg = proj.months[11].investment_value
        assert agg.quantize(Decimal("0.01")) == Decimal("3240.00")
        # Aggregate at final month == ending_investment_value
        assert proj.ending_investment_value.quantize(Decimal("0.01")) == Decimal(
            "3240.00"
        )

    def test_contribution_flows_into_outflow(self):
        """A 500/mo contribution drops cash by 500 each month — no lines needed."""
        profile = make_profile(opening="10000", horizon=6)
        inv = make_investment(
            1, "IRA", starting="0", contribution="500", rate_pct="0"
        )
        proj = project(profile, [], (), [inv])

        for m, mc in enumerate(proj.months):
            assert mc.total_inflow == Decimal("0")
            assert mc.total_outflow == Decimal("500")
            assert mc.net == Decimal("-500")
            # Cash drains: 10000 - (m+1)*500
            assert mc.closing_balance == Decimal(10000 - (m + 1) * 500)

        # Total outflow across horizon = total contributed
        assert proj.total_outflow == Decimal("3000")  # 6 * 500
        assert proj.total_investment_contrib == Decimal("3000")


def make_investment_override(
    investment_id: int,
    month_offset: int,
    amount: str,
    effect_span: str = "single_month",
) -> InvestmentOverrideInput:
    return InvestmentOverrideInput(
        investment_id=investment_id,
        month_offset=month_offset,
        amount=Decimal(amount),
        effect_span=effect_span,
    )


class TestInvestmentOverrides:
    """Per-investment contribution overrides, matching line-override semantics."""

    def test_single_month_override_replaces_one_month(self):
        """A single_month override only changes the target month's contribution."""
        profile = make_profile(opening="10000", horizon=6)
        inv = make_investment(
            1, "IRA", starting="0", contribution="500", rate_pct="0"
        )
        ovr = make_investment_override(1, month_offset=2, amount="0")
        proj = project(profile, [], (), [inv], [ovr])

        # Month 2: contribution is 0 (overridden); other months: 500.
        expected = [500, 500, 0, 500, 500, 500]
        for m, exp in enumerate(expected):
            assert proj.months[m].investments[1].contribution == Decimal(exp)
            assert proj.months[m].investment_contributions == Decimal(exp)
            assert proj.months[m].total_outflow == Decimal(exp)

        # Only month 2 flagged as overridden
        assert proj.months[2].investments[1].is_overridden is True
        assert proj.months[0].investments[1].is_overridden is False
        # Base contribution preserved for display
        assert proj.months[2].investments[1].base_contribution == Decimal("500")

        # Summary: 5 * 500 contributed (one month skipped), override_count=1.
        summary = proj.investment_summaries[0]
        assert summary.total_contributed == Decimal("2500")
        assert summary.override_count == 1

    def test_until_next_override_applies_forward(self):
        """An until_next override applies from start through remaining horizon."""
        profile = make_profile(opening="10000", horizon=6)
        inv = make_investment(
            1, "IRA", starting="0", contribution="500", rate_pct="0"
        )
        ovr = make_investment_override(
            1, month_offset=2, amount="1000", effect_span="until_next"
        )
        proj = project(profile, [], (), [inv], [ovr])

        expected = [500, 500, 1000, 1000, 1000, 1000]
        for m, exp in enumerate(expected):
            assert proj.months[m].investments[1].contribution == Decimal(exp)

        summary = proj.investment_summaries[0]
        assert summary.total_contributed == Decimal("5000")
        # 4 months active under the override
        assert summary.override_count == 4

    def test_until_next_then_single_month_precedence(self):
        """A single_month at month K wins over an active until_next at K."""
        profile = make_profile(opening="0", horizon=6)
        inv = make_investment(
            1, "IRA", starting="0", contribution="500", rate_pct="0"
        )
        step = make_investment_override(
            1, month_offset=1, amount="1000", effect_span="until_next"
        )
        spike = make_investment_override(
            1, month_offset=3, amount="250", effect_span="single_month"
        )
        proj = project(profile, [], (), [inv], [step, spike])

        # Month 0: base 500; months 1,2,4,5: step 1000; month 3: spike 250.
        expected = [500, 1000, 1000, 250, 1000, 1000]
        for m, exp in enumerate(expected):
            assert proj.months[m].investments[1].contribution == Decimal(exp)

    def test_later_until_next_replaces_earlier(self):
        """A second until_next supersedes the first from its start month."""
        profile = make_profile(opening="0", horizon=6)
        inv = make_investment(
            1, "IRA", starting="0", contribution="500", rate_pct="0"
        )
        step1 = make_investment_override(
            1, month_offset=1, amount="1000", effect_span="until_next"
        )
        step2 = make_investment_override(
            1, month_offset=4, amount="200", effect_span="until_next"
        )
        proj = project(profile, [], (), [inv], [step1, step2])

        expected = [500, 1000, 1000, 1000, 200, 200]
        for m, exp in enumerate(expected):
            assert proj.months[m].investments[1].contribution == Decimal(exp)

    def test_override_outside_horizon_is_ignored(self):
        """An override at month >= horizon is dropped, not applied."""
        profile = make_profile(opening="0", horizon=3)
        inv = make_investment(
            1, "IRA", starting="0", contribution="500", rate_pct="0"
        )
        ovr = make_investment_override(1, month_offset=5, amount="0")
        proj = project(profile, [], (), [inv], [ovr])

        for m in range(3):
            assert proj.months[m].investments[1].contribution == Decimal("500")
        summary = proj.investment_summaries[0]
        assert summary.override_count == 0

    def test_override_affects_growth_via_rolling_balance(self):
        """Overrides feed into the compounded balance — higher contrib grows
        the balance faster.
        """
        profile = make_profile(opening="0", horizon=3)
        inv = make_investment(
            1, "IRA", starting="1000", contribution="100", rate_pct="0"
        )
        ovr = make_investment_override(
            1, month_offset=0, amount="500", effect_span="until_next"
        )
        proj = project(profile, [], (), [inv], [ovr])

        # 0% growth, 500/mo contribution, starting 1000 -> 1500, 2000, 2500.
        assert proj.months[0].investments[1].closing_balance == Decimal("1500")
        assert proj.months[1].investments[1].closing_balance == Decimal("2000")
        assert proj.months[2].investments[1].closing_balance == Decimal("2500")


class TestTaxIntegration:
    """Engine-level integration: salary line + attached tax profile.

    Verifies that projection inflow is net of tax and that per-line
    LineMonth records carry gross + income_tax + ni for drill-down.
    """

    def _scotland_tp(self, *, apply_income_tax=True, apply_ni=True):
        return TaxProfileInput(
            id=1,
            name="Scotland",
            jurisdiction="scotland",
            apply_income_tax=apply_income_tax,
            apply_ni=apply_ni,
        )

    def _line_with_tax(self, *, start=0, end=11, amount="5000"):
        line = LineInput(
            id=1,
            label="Salary",
            kind="inflow",
            amount=Decimal(amount),
            start_month_offset=start,
            end_month_offset=end,
            tax_profile=self._scotland_tp(),
        )
        return line

    def test_inflow_is_net_of_tax(self):
        profile = make_profile(opening="0", horizon=12, start=date(2025, 4, 1))
        line = self._line_with_tax()
        proj = project(profile, [line])
        # Gross £60k; Scottish IT = 13,228.31; NI = 267.50 × 12 = 3,210.
        # Net total = 60,000 - 13,228.31 - 3,210 = 43,561.69.
        # (Engine keeps full precision; UI/export rounds at 2dp.)
        assert proj.total_inflow.quantize(Decimal("0.01")) == Decimal("43561.69")

    def test_line_month_records_gross_and_breakdown(self):
        profile = make_profile(opening="0", horizon=12, start=date(2025, 4, 1))
        line = self._line_with_tax()
        proj = project(profile, [line])

        m0 = proj.months[0]
        lm = m0.line_contributions[1]
        assert lm.gross_amount == Decimal("5000")
        # IT per month (first 11) = annual / 12
        assert lm.income_tax == Decimal("13228.31") / 12
        assert lm.ni == Decimal("267.50")
        # Effective (net) = gross - it - ni
        assert lm.effective_amount == lm.gross_amount - lm.income_tax - lm.ni

    def test_untaxed_line_unaffected(self):
        profile = make_profile(opening="0", horizon=12, start=date(2025, 4, 1))
        taxed = self._line_with_tax()
        untaxed = LineInput(
            id=2,
            label="Other inflow",
            kind="inflow",
            amount=Decimal("1000"),
            start_month_offset=0,
            end_month_offset=11,
        )
        proj = project(profile, [taxed, untaxed])
        # Untaxed line contributes 12k unchanged; taxed line contributes net.
        # total_inflow = 12,000 + 43,561.69 = 55,561.69
        assert proj.total_inflow.quantize(Decimal("0.01")) == Decimal("55561.69")
        # Untaxed line_contributions shows no gross / zero tax.
        lm_untaxed = proj.months[0].line_contributions[2]
        assert lm_untaxed.gross_amount is None
        assert lm_untaxed.income_tax == Decimal("0")
        assert lm_untaxed.ni == Decimal("0")
        assert lm_untaxed.effective_amount == Decimal("1000")

    def test_bonus_override_flows_into_tax(self):
        profile = make_profile(opening="0", horizon=12, start=date(2025, 4, 1))
        line = self._line_with_tax()
        override = OverrideInput(
            line_id=1, month_offset=5, amount=Decimal("10000")
        )
        proj = project(profile, [line], overrides=[override])
        # NI on bonus month = 367.50 (previously computed).
        bonus = proj.months[5].line_contributions[1]
        assert bonus.gross_amount == Decimal("10000")
        assert bonus.ni == Decimal("367.50")

    def test_disabled_ni_zero_ni(self):
        profile = make_profile(opening="0", horizon=12, start=date(2025, 4, 1))
        line = LineInput(
            id=1,
            label="Salary",
            kind="inflow",
            amount=Decimal("5000"),
            start_month_offset=0,
            end_month_offset=11,
            tax_profile=self._scotland_tp(apply_ni=False),
        )
        proj = project(profile, [line])
        for m in proj.months:
            assert m.line_contributions[1].ni == Decimal("0")

    def test_fallback_warning_surfaces(self):
        # Profile starts in April 2030 — no table; fallback warns.
        profile = make_profile(opening="0", horizon=12, start=date(2030, 4, 1))
        line = self._line_with_tax()
        proj = project(profile, [line])
        assert proj.warnings
        assert any("2030-31" in w for w in proj.warnings)

    def test_no_warnings_when_all_years_known(self):
        profile = make_profile(opening="0", horizon=12, start=date(2025, 4, 1))
        line = self._line_with_tax()
        proj = project(profile, [line])
        assert proj.warnings == []


class TestOverrideResolver:
    """Verifies the single_month / until_next precedence rules and their
    interaction with the tax engine.

    Scenario setup: one 12-month inflow line, base £1,000. Profile opening
    is zero so ``total_inflow`` alone signals the per-month effective amounts.
    """

    def _profile(self):
        return make_profile(opening="0", horizon=12)

    def _line(self):
        return make_line(1, "Base", "inflow", "1000", start=0, end=11)

    def test_single_month_only_applies_to_that_month(self):
        proj = project(
            self._profile(),
            [self._line()],
            overrides=[
                OverrideInput(
                    line_id=1,
                    month_offset=3,
                    amount=Decimal("1500"),
                    effect_span="single_month",
                )
            ],
        )
        # 11 months at £1000 + 1 month at £1500 = £12,500.
        assert proj.total_inflow == Decimal("12500")
        assert proj.months[3].total_inflow == Decimal("1500")
        assert proj.months[4].total_inflow == Decimal("1000")

    def test_until_next_applies_from_start_to_end(self):
        proj = project(
            self._profile(),
            [self._line()],
            overrides=[
                OverrideInput(
                    line_id=1,
                    month_offset=3,
                    amount=Decimal("1500"),
                    effect_span="until_next",
                )
            ],
        )
        # Months 0..2 at £1000 = £3,000; months 3..11 at £1500 = £13,500.
        assert proj.total_inflow == Decimal("16500")
        assert proj.months[2].total_inflow == Decimal("1000")
        assert proj.months[3].total_inflow == Decimal("1500")
        assert proj.months[11].total_inflow == Decimal("1500")

    def test_two_until_next_steps_chain(self):
        proj = project(
            self._profile(),
            [self._line()],
            overrides=[
                OverrideInput(
                    line_id=1,
                    month_offset=3,
                    amount=Decimal("1500"),
                    effect_span="until_next",
                ),
                OverrideInput(
                    line_id=1,
                    month_offset=8,
                    amount=Decimal("2000"),
                    effect_span="until_next",
                ),
            ],
        )
        # 0..2 → 1000 (3 months = 3000)
        # 3..7 → 1500 (5 months = 7500)
        # 8..11 → 2000 (4 months = 8000)
        assert proj.total_inflow == Decimal("18500")
        assert proj.months[2].total_inflow == Decimal("1000")
        assert proj.months[3].total_inflow == Decimal("1500")
        assert proj.months[7].total_inflow == Decimal("1500")
        assert proj.months[8].total_inflow == Decimal("2000")
        assert proj.months[11].total_inflow == Decimal("2000")

    def test_single_punches_through_until_next(self):
        # Step at 3 → £1500 onward. Single override at 5 → £800 just that
        # month. Month 6 must return to the step's £1500.
        proj = project(
            self._profile(),
            [self._line()],
            overrides=[
                OverrideInput(
                    line_id=1,
                    month_offset=3,
                    amount=Decimal("1500"),
                    effect_span="until_next",
                ),
                OverrideInput(
                    line_id=1,
                    month_offset=5,
                    amount=Decimal("800"),
                    effect_span="single_month",
                ),
            ],
        )
        assert proj.months[4].total_inflow == Decimal("1500")
        assert proj.months[5].total_inflow == Decimal("800")
        assert proj.months[6].total_inflow == Decimal("1500")

    def test_deletion_semantics_by_absence(self):
        # Same as test_until_next_applies_from_start_to_end but removing the
        # override reverts all months to base — confirms deletion needs no
        # special handling; the resolver just looks at what's present.
        proj = project(self._profile(), [self._line()], overrides=[])
        assert proj.total_inflow == Decimal("12000")  # 12 × 1000
        for m in proj.months:
            assert m.total_inflow == Decimal("1000")

    def test_overrides_outside_line_window_ignored(self):
        line = make_line(1, "Short", "inflow", "1000", start=2, end=5)
        proj = project(
            make_profile(opening="0", horizon=12),
            [line],
            overrides=[
                OverrideInput(
                    line_id=1,
                    month_offset=0,  # before line start
                    amount=Decimal("5000"),
                    effect_span="until_next",
                ),
                OverrideInput(
                    line_id=1,
                    month_offset=8,  # after line end
                    amount=Decimal("5000"),
                    effect_span="single_month",
                ),
            ],
        )
        # Neither override is in the active window → line runs at base only.
        assert proj.total_inflow == Decimal("4000")  # months 2..5 × 1000

    def test_until_next_integrates_with_tax(self):
        """A step salary raise mid-year: step months pay more IT than
        non-step months (base-plus-delta), via the same tax pipeline.
        """
        tp = TaxProfileInput(
            id=1,
            name="Scotland",
            jurisdiction="scotland",
            apply_income_tax=True,
            apply_ni=False,
        )
        line = LineInput(
            id=1,
            label="Salary",
            kind="inflow",
            amount=Decimal("3000"),
            start_month_offset=0,
            end_month_offset=11,
            tax_profile=tp,
        )
        profile = make_profile(opening="0", horizon=12, start=date(2025, 4, 1))
        proj = project(
            profile,
            [line],
            overrides=[
                OverrideInput(
                    line_id=1,
                    month_offset=6,
                    amount=Decimal("4000"),
                    effect_span="until_next",
                )
            ],
        )
        # Non-step months (0..5): IT = baseline (36k annual / 12).
        # Step months (6..11): IT = baseline + delta_share.
        lm0 = proj.months[0].line_contributions[1]
        lm6 = proj.months[6].line_contributions[1]
        # The step bumps annual gross → step months must pay MORE IT.
        assert lm6.income_tax > lm0.income_tax
        # Non-step months retain base-level IT (matches no-step scenario).
        baseline_it = Decimal("4757.33") / 12
        assert lm0.income_tax == baseline_it
