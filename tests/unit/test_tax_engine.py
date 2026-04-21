"""Unit tests for the pure tax engine (tax_engine + tax_tables).

Covers:
  - Band walker correctness at boundary values.
  - PA taper at £100k / £125,140+ (full loss).
  - tax_year_key at April boundary.
  - compute_line_tax: full year, mid-year start, cross-tax-year span,
    bonus month (NI per-month threshold crossing), zero-gross override,
    unknown tax year fallback warning.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ledger.services.tax_engine import (
    compute_line_tax,
    compute_progressive_tax,
    group_months_by_tax_year,
    tax_year_key,
)
from ledger.services.tax_tables import (
    NI_EMPLOYEE,
    RUK_INCOME_TAX,
    SCOTLAND_INCOME_TAX,
    get_income_tax_bands,
    get_ni_bands,
)


def _d(s: str | int | float) -> Decimal:
    return Decimal(str(s))


# ---------- tax_year_key ----------

class TestTaxYearKey:
    def test_april_onwards_is_starting_year(self):
        assert tax_year_key(2026, 4) == "2026-27"
        assert tax_year_key(2026, 12) == "2026-27"

    def test_jan_to_march_is_previous_starting_year(self):
        assert tax_year_key(2026, 1) == "2025-26"
        assert tax_year_key(2026, 3) == "2025-26"

    def test_april_boundary(self):
        assert tax_year_key(2026, 3) == "2025-26"
        assert tax_year_key(2026, 4) == "2026-27"

    def test_two_digit_wraps(self):
        assert tax_year_key(2099, 4) == "2099-00"


# ---------- group_months_by_tax_year ----------

class TestGroupByTaxYear:
    def test_single_tax_year_april_start(self):
        # Profile starts April 2026, 12 months → all in 2026-27.
        groups = group_months_by_tax_year(date(2026, 4, 1), range(12))
        assert groups == {"2026-27": list(range(12))}

    def test_crosses_tax_year_when_starting_january(self):
        # Profile starts January 2026; first 3 months (Jan–Mar) are 2025-26,
        # next 9 (Apr–Dec) are 2026-27.
        groups = group_months_by_tax_year(date(2026, 1, 1), range(12))
        assert groups == {
            "2025-26": [0, 1, 2],
            "2026-27": [3, 4, 5, 6, 7, 8, 9, 10, 11],
        }

    def test_spans_three_tax_years(self):
        # Start June 2026 (in 2026-27), 24 months.
        # Jun 2026 – Mar 2027 = 2026-27 (10 months, offsets 0..9)
        # Apr 2027 – Mar 2028 = 2027-28 (12 months, offsets 10..21)
        # Apr 2028 – May 2028 = 2028-29 (2 months, offsets 22..23)
        groups = group_months_by_tax_year(date(2026, 6, 1), range(24))
        assert groups["2026-27"] == list(range(10))
        assert groups["2027-28"] == list(range(10, 22))
        assert groups["2028-29"] == [22, 23]


# ---------- compute_progressive_tax ----------

class TestComputeProgressiveTax:
    def test_zero_earnings(self):
        bands = SCOTLAND_INCOME_TAX["2025-26"]
        assert compute_progressive_tax(_d(0), bands) == 0

    def test_below_pa(self):
        bands = SCOTLAND_INCOME_TAX["2025-26"]
        assert compute_progressive_tax(_d(10000), bands) == 0

    def test_scotland_30k(self):
        # £30k gross. After £12,570 PA: £17,430 taxable.
        # Starter: £2,306 @ 19% = £438.14
        # Basic: £11,685 @ 20% = £2,337.00
        # Intermediate: remaining £3,439 @ 21% = £722.19
        # Total: £3,497.33
        bands = SCOTLAND_INCOME_TAX["2025-26"]
        result = compute_progressive_tax(_d(30000), bands)
        assert result == _d("3497.33")

    def test_scotland_60k(self):
        # £60k gross. After £12,570 PA: £47,430 taxable.
        # Starter: 2,306 @ 19% = 438.14
        # Basic:   11,685 @ 20% = 2,337.00
        # Intermediate: 17,101 @ 21% = 3,591.21
        # Higher: remaining 16,338 @ 42% = 6,861.96
        # Total: 13,228.31
        bands = SCOTLAND_INCOME_TAX["2025-26"]
        result = compute_progressive_tax(_d(60000), bands)
        assert result == _d("13228.31")

    def test_ruk_60k(self):
        # £60k, rUK. After £12,570 PA: £47,430 taxable.
        # Basic: 37,700 @ 20% = 7,540.00
        # Higher: remaining 9,730 @ 40% = 3,892.00
        # Total: 11,432.00
        bands = RUK_INCOME_TAX["2025-26"]
        result = compute_progressive_tax(_d(60000), bands)
        assert result == _d("11432.00")

    def test_pa_taper_below_threshold(self):
        # £95k — below £100k taper, full PA applies.
        bands = SCOTLAND_INCOME_TAX["2025-26"]
        # Manual: 95,000 - 12,570 = 82,430 taxable.
        # Starter 2306 @ 19%   = 438.14
        # Basic 11685 @ 20%    = 2,337.00
        # Intermediate 17101 @ 21% = 3,591.21
        # Higher: 82,430 - 31,092 = 51,338; cap 31,338 @ 42% = 13,161.96
        # Advanced: remainder 20,000 @ 45% = 9,000.00
        # Wait: Higher band upper is 62,430. So higher gets 62,430-31,092=31,338 @ 42%
        # Then advanced: 82,430-62,430 = 20,000 @ 45% = 9,000
        # Total: 438.14 + 2337 + 3591.21 + 13161.96 + 9000 = 28,528.31
        result = compute_progressive_tax(_d(95000), bands)
        assert result == _d("28528.31")

    def test_pa_taper_activated(self):
        # £110k: taper reduces PA by (110k - 100k)/2 = £5,000.
        # Effective PA = 12,570 - 5,000 = 7,570.
        # Taxable = 110,000 - 7,570 = 102,430.
        bands = SCOTLAND_INCOME_TAX["2025-26"]
        result = compute_progressive_tax(_d(110000), bands)
        # Compute expected:
        # Starter 2306 @ 19% = 438.14
        # Basic 11685 @ 20% = 2337.00
        # Intermediate 17101 @ 21% = 3591.21
        # Higher 31338 @ 42% = 13161.96
        # Advanced: 102,430 - 62,430 = 40,000 @ 45% = 18,000.00
        # Total: 37,528.31
        assert result == _d("37528.31")

    def test_pa_taper_full_loss(self):
        # £125,140+ → PA fully gone.
        bands = SCOTLAND_INCOME_TAX["2025-26"]
        result = compute_progressive_tax(_d(125140), bands)
        # Taxable = 125,140 (no allowance).
        # Starter 2306 @ 19% = 438.14
        # Basic 11685 @ 20% = 2337.00
        # Intermediate 17101 @ 21% = 3591.21
        # Higher 31338 @ 42% = 13161.96
        # Advanced 50140 @ 45% = 22,563.00
        # Top 12,570 @ 48% = 6,033.60
        # Total: 48,124.91
        assert result == _d("48124.91")

    def test_ni_at_pt_exactly(self):
        # Monthly gross = PT = £1,048 → zero NI.
        ni_bands = NI_EMPLOYEE["2025-26"]
        assert compute_progressive_tax(_d(1048), ni_bands) == 0

    def test_ni_between_pt_and_uel(self):
        # £3,000/month: (3000 - 1048) @ 8% = 156.16
        ni_bands = NI_EMPLOYEE["2025-26"]
        result = compute_progressive_tax(_d(3000), ni_bands)
        assert result == _d("156.16")

    def test_ni_crosses_uel(self):
        # £10,000/month bonus. PT=1048, UEL=4189.
        # Between PT and UEL: 3,141 @ 8% = 251.28
        # Above UEL: 5,811 @ 2% = 116.22
        # Total: 367.50
        ni_bands = NI_EMPLOYEE["2025-26"]
        result = compute_progressive_tax(_d(10000), ni_bands)
        assert result == _d("367.50")


# ---------- table lookup + fallback ----------

class TestTableLookup:
    def test_known_year_no_fallback(self):
        bands, is_fallback = get_income_tax_bands("scotland", "2025-26")
        assert bands is SCOTLAND_INCOME_TAX["2025-26"]
        assert is_fallback is False

    def test_unknown_year_falls_back(self):
        bands, is_fallback = get_income_tax_bands("scotland", "2030-31")
        assert bands is SCOTLAND_INCOME_TAX["2025-26"]
        assert is_fallback is True

    def test_ni_unknown_year_falls_back(self):
        _, is_fallback = get_ni_bands("2030-31")
        assert is_fallback is True

    def test_unknown_jurisdiction_raises(self):
        with pytest.raises(ValueError):
            get_income_tax_bands("northern_ireland", "2025-26")


# ---------- compute_line_tax (integration of all above) ----------

class TestComputeLineTax:
    def test_full_year_april_start_scotland(self):
        # £60k salary = £5,000/mo. April start = full 2026-27 year.
        gross = {m: _d(5000) for m in range(12)}
        per_month, warnings = compute_line_tax(
            profile_start_date=date(2025, 4, 1),
            monthly_gross_by_offset=gross,
            base_monthly_amount=_d(5000),
            jurisdiction="scotland",
            apply_income_tax=True,
            apply_ni=True,
        )
        assert warnings == []
        # Total annual IT = compute_progressive_tax(60000, scot bands) = 13,228.31
        total_it = sum(it for (it, _ni) in per_month.values())
        assert total_it.quantize(_d("0.01")) == _d("13228.31")
        # Each month IT is 13,228.31/12. With no overrides (gross == base),
        # allocation falls through to proportional-to-gross which gives an
        # even split.
        first_11_it = [per_month[m][0] for m in range(11)]
        for it in first_11_it:
            assert it == _d("13228.31") / 12
        # NI per month = (5000-1048) @ 8% + 0 above UEL = 3,141 @ 8% + 811 @ 2%
        # = 251.28 + 16.22 = 267.50
        for m in range(12):
            assert per_month[m][1] == _d("267.50")

    def test_mid_year_start_january(self):
        # Profile starts January 2026. Salary £5k/mo for 3 months (Jan–Mar).
        # These 3 months are all in tax year 2025-26 (Jan/Feb/Mar fall in
        # the tax year that started April 2025).
        # Segment gross = £15k. PA £12,570 absorbs most → taxable £2,430.
        # Scottish starter band up to £2,306 @ 19% = £438.14
        # Basic: remaining 124 @ 20% = 24.80
        # Total IT = 462.94. Split across 3 months.
        gross = {m: _d(5000) for m in range(3)}
        per_month, warnings = compute_line_tax(
            profile_start_date=date(2026, 1, 1),
            monthly_gross_by_offset=gross,
            base_monthly_amount=_d(5000),
            jurisdiction="scotland",
            apply_income_tax=True,
            apply_ni=True,
        )
        assert warnings == []
        total_it = sum(it for (it, _ni) in per_month.values())
        assert total_it.quantize(_d("0.01")) == _d("462.94")
        # Each month 462.94 / 3 = 154.3133...
        assert per_month[0][0] == _d("462.94") / 3
        assert per_month[1][0] == _d("462.94") / 3
        # Total matches to the penny after 2dp quantize.
        total = sum((per_month[m][0] for m in range(3)), _d("0"))
        assert total.quantize(_d("0.01")) == _d("462.94")

    def test_cross_tax_year_span(self):
        # Profile starts January 2026; salary runs 6 months (Jan–June).
        # Jan, Feb, Mar = tax year 2025-26 (3 months × £5k = £15k)
        # Apr, May, Jun = tax year 2026-27 (3 months × £5k = £15k)
        # Each segment gets its own full PA.
        gross = {m: _d(5000) for m in range(6)}
        per_month, _ = compute_line_tax(
            profile_start_date=date(2026, 1, 1),
            monthly_gross_by_offset=gross,
            base_monthly_amount=_d(5000),
            jurisdiction="scotland",
            apply_income_tax=True,
            apply_ni=False,
        )
        # Segment 1 (0,1,2): total IT = 462.94 (as above).
        # Segment 2 (3,4,5): same — another 462.94.
        seg1 = sum((per_month[m][0] for m in range(3)), _d("0"))
        seg2 = sum((per_month[m][0] for m in range(3, 6)), _d("0"))
        assert seg1.quantize(_d("0.01")) == _d("462.94")
        assert seg2.quantize(_d("0.01")) == _d("462.94")

    def test_bonus_month_ni(self):
        # 11 regular months at £5k + 1 bonus month at £10k.
        gross = {m: _d(5000) for m in range(12)}
        gross[5] = _d(10000)
        per_month, _ = compute_line_tax(
            profile_start_date=date(2025, 4, 1),
            monthly_gross_by_offset=gross,
            base_monthly_amount=_d(5000),
            jurisdiction="scotland",
            apply_income_tax=True,
            apply_ni=True,
        )
        # Bonus month NI = 367.50 (from earlier calc)
        assert per_month[5][1] == _d("367.50")
        # Regular month NI unaffected
        assert per_month[0][1] == _d("267.50")
        # Income tax now reflects £65k annual gross, split evenly across 12.

    def test_zero_gross_override_month(self):
        # 11 regular + 1 zero month in middle. NI on zero month = 0.
        gross = {m: _d(5000) for m in range(12)}
        gross[6] = _d(0)
        per_month, _ = compute_line_tax(
            profile_start_date=date(2025, 4, 1),
            monthly_gross_by_offset=gross,
            base_monthly_amount=_d(5000),
            jurisdiction="scotland",
            apply_income_tax=True,
            apply_ni=True,
        )
        # Zero-gross month → NI is zero (monthly threshold not met).
        assert per_month[6][1] == 0
        # The override month absorbs the annual tax reduction (a smaller total
        # annual gross means less annual tax). Since the month's share would
        # go negative, it's clamped at zero. Non-override months retain the
        # baseline IT they'd have paid at full salary.
        assert per_month[6][0] == 0
        # Other months pay the baseline rate for base_monthly salary.
        baseline_it = _d("13228.31") / 12  # £60k annual / 12
        assert per_month[0][0] == baseline_it

    def test_unknown_year_emits_warning(self):
        gross = {m: _d(5000) for m in range(12)}
        _, warnings = compute_line_tax(
            profile_start_date=date(2030, 4, 1),  # no 2030-31 table
            monthly_gross_by_offset=gross,
            base_monthly_amount=_d(5000),
            jurisdiction="scotland",
            apply_income_tax=True,
            apply_ni=True,
        )
        # Should warn about income tax fallback AND NI fallback — but we
        # dedupe by year so one warning per year suffices (IT warning wins).
        assert len(warnings) >= 1
        assert "2030-31" in warnings[0]

    def test_toggles_disable_both(self):
        gross = {m: _d(5000) for m in range(12)}
        per_month, _ = compute_line_tax(
            profile_start_date=date(2025, 4, 1),
            monthly_gross_by_offset=gross,
            base_monthly_amount=_d(5000),
            jurisdiction="scotland",
            apply_income_tax=False,
            apply_ni=False,
        )
        for m in range(12):
            assert per_month[m] == (Decimal("0"), Decimal("0"))

    def test_empty_gross(self):
        per_month, warnings = compute_line_tax(
            profile_start_date=date(2025, 4, 1),
            monthly_gross_by_offset={},
            base_monthly_amount=_d(5000),
            jurisdiction="scotland",
            apply_income_tax=True,
            apply_ni=True,
        )
        assert per_month == {}
        assert warnings == []

    def test_bonus_leaves_non_bonus_months_unchanged(self):
        """Regression: changing a bonus override must not change non-bonus
        months' IT. User report: overriding Jan to £5k vs £8k changed every
        month's net. The base-plus-delta allocation fixes that.
        """
        # Base £3k/mo over a full tax year.
        base = _d(3000)
        gross_5k = {m: base for m in range(12)}
        gross_5k[9] = _d(5000)  # Jan 2026 (offset 9 of April 2025 start)
        gross_8k = {m: base for m in range(12)}
        gross_8k[9] = _d(8000)

        it_5k, _ = compute_line_tax(
            profile_start_date=date(2025, 4, 1),
            monthly_gross_by_offset=gross_5k,
            base_monthly_amount=base,
            jurisdiction="scotland",
            apply_income_tax=True,
            apply_ni=False,
        )
        it_8k, _ = compute_line_tax(
            profile_start_date=date(2025, 4, 1),
            monthly_gross_by_offset=gross_8k,
            base_monthly_amount=base,
            jurisdiction="scotland",
            apply_income_tax=True,
            apply_ni=False,
        )
        # Non-bonus months must be identical in both scenarios.
        for m in range(12):
            if m == 9:
                continue
            assert it_5k[m][0] == it_8k[m][0], (
                f"Month {m} IT changed when bonus changed from 5k to 8k"
            )
        # Bonus month must differ (absorbed the extra tax).
        assert it_5k[9][0] != it_8k[9][0]
        # And the non-bonus months pay the baseline per-month (what they'd
        # pay on a flat £3k/mo year).
        # Base annual gross = £36k. Baseline IT = 4,757.33 (computed).
        # Per month = 4,757.33 / 12.
        baseline_per_month = _d("4757.33") / 12
        assert it_5k[0][0] == baseline_per_month

    def test_pa_taper_activated_by_bonus(self):
        # Base £95k annual (below taper). Add a £20k bonus → £115k gross.
        # Taper: (115000 - 100000)/2 = 7,500 PA reduction.
        # Effective PA = 5,070.
        # Manually computed annual IT > plain £95k IT.
        gross_base = {m: _d(95000) / 12 for m in range(12)}
        gross_bonus = dict(gross_base)
        gross_bonus[5] = gross_base[5] + _d(20000)

        per_month_base, _ = compute_line_tax(
            profile_start_date=date(2025, 4, 1),
            monthly_gross_by_offset=gross_base,
            base_monthly_amount=_d(95000) / 12,
            jurisdiction="scotland",
            apply_income_tax=True,
            apply_ni=False,
        )
        per_month_bonus, _ = compute_line_tax(
            profile_start_date=date(2025, 4, 1),
            monthly_gross_by_offset=gross_bonus,
            base_monthly_amount=_d(95000) / 12,
            jurisdiction="scotland",
            apply_income_tax=True,
            apply_ni=False,
        )
        total_base = sum(it for (it, _ni) in per_month_base.values())
        total_bonus = sum(it for (it, _ni) in per_month_bonus.values())
        # Taper kicks in on the bonus case: effective tax > base + (bonus × top band)
        # Marginal rate on bonus should be higher than 42% due to lost PA.
        marginal = total_bonus - total_base
        # Plain higher-rate would be 20k × 42% = £8,400. Taper adds effectively
        # 7,500 × 42% = 3,150 because PA lost is taxed at the top applicable
        # rate of the bonus range (higher = 42%). So marginal ≈ 11,550.
        assert marginal > _d("8400")
