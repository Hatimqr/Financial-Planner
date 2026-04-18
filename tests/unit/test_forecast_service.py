"""Tests for ForecastService — CRUD, validation, projection, and export."""

import json
from datetime import date
from decimal import Decimal

import pytest

from ledger.db.forecast_models import ForecastProfile
from ledger.services.forecast_service import ForecastService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_profile(service: ForecastService, **overrides) -> ForecastProfile:
    """Build a baseline NYUAD-style profile; callers override specifics."""
    defaults = dict(
        name="NYUAD RA",
        currency="AED",
        start_date=date(2026, 6, 1),
        horizon_months=7,
        opening_balance=Decimal("5000"),
        notes=None,
    )
    defaults.update(overrides)
    return service.create_profile(**defaults)


def _add_nyuad_lines(service: ForecastService, profile_id: int) -> dict:
    """Standard NYUAD setup used by integration tests. Returns {salary, rent, groceries}."""
    salary = service.add_line(
        profile_id, "Salary", "inflow", Decimal("10000"), 0, 6
    )
    rent = service.add_line(
        profile_id, "Rent", "outflow", Decimal("4000"), 0, 6
    )
    groceries = service.add_line(
        profile_id, "Groceries", "outflow", Decimal("800"), 0, 6
    )
    return {"salary": salary, "rent": rent, "groceries": groceries}


# ---------------------------------------------------------------------------
# Profile CRUD & validation
# ---------------------------------------------------------------------------


class TestProfileCRUD:
    def test_create_basic(self, session):
        service = ForecastService(session)
        profile = _make_profile(service)

        assert profile.id is not None
        assert profile.name == "NYUAD RA"
        assert profile.currency == "AED"
        assert profile.horizon_months == 7
        assert profile.opening_balance == Decimal("5000")
        assert profile.created_at is not None

    def test_create_trims_and_uppercases_currency(self, session):
        service = ForecastService(session)
        profile = service.create_profile(
            name="  Test  ",
            currency=" aed ",
            start_date=date(2026, 6, 1),
            horizon_months=1,
            opening_balance=Decimal("0"),
        )
        assert profile.name == "Test"
        assert profile.currency == "AED"

    def test_create_rejects_blank_name(self, session):
        service = ForecastService(session)
        with pytest.raises(ValueError, match="name cannot be empty"):
            _make_profile(service, name="   ")

    def test_create_rejects_blank_currency(self, session):
        service = ForecastService(session)
        with pytest.raises(ValueError, match="currency cannot be empty"):
            _make_profile(service, currency=" ")

    def test_create_rejects_zero_horizon(self, session):
        service = ForecastService(session)
        with pytest.raises(ValueError, match="positive integer"):
            _make_profile(service, horizon_months=0)

    def test_create_rejects_negative_horizon(self, session):
        service = ForecastService(session)
        with pytest.raises(ValueError, match="positive integer"):
            _make_profile(service, horizon_months=-3)

    def test_create_rejects_non_first_of_month(self, session):
        service = ForecastService(session)
        with pytest.raises(ValueError, match="first of the month"):
            _make_profile(service, start_date=date(2026, 6, 15))

    def test_get_and_list(self, session):
        service = ForecastService(session)
        a = _make_profile(service, name="B profile")
        _make_profile(service, name="a profile")  # lowercase-first to check sort

        assert service.get_profile(a.id) is a
        assert service.get_profile(9999) is None

        listed = service.list_profiles()
        assert [p.name for p in listed] == ["a profile", "B profile"]

    def test_update_partial(self, session):
        service = ForecastService(session)
        profile = _make_profile(service)

        result = service.update_profile(profile.id, name="Renamed", notes="note")

        assert result.profile.name == "Renamed"
        assert result.profile.notes == "note"
        assert result.profile.currency == "AED"  # untouched
        assert result.lines_truncated == []
        assert result.overrides_deleted == 0

    def test_update_horizon_shrink_truncates_lines(self, session):
        service = ForecastService(session)
        profile = _make_profile(service, horizon_months=12)
        lines = _add_nyuad_lines(service, profile.id)
        # Extend salary to month 11 so shrink affects it.
        service.update_line(
            lines["salary"].id, end_month_offset=11
        )

        result = service.update_profile(profile.id, horizon_months=5)

        assert result.profile.horizon_months == 5
        assert lines["salary"].id in result.lines_truncated
        # Salary's end is clamped to 4 (= new_horizon - 1).
        refreshed = service.line_repo.get_by_id(lines["salary"].id)
        assert refreshed.end_month_offset == 4

    def test_update_horizon_shrink_deletes_overrides_outside_new_window(self, session):
        service = ForecastService(session)
        profile = _make_profile(service, horizon_months=12)
        lines = _add_nyuad_lines(service, profile.id)
        service.update_line(lines["salary"].id, end_month_offset=11)
        # Override on month 8 will be outside the new window when we shrink to 5.
        service.add_override(lines["salary"].id, 8, Decimal("12000"))

        result = service.update_profile(profile.id, horizon_months=5)

        assert result.overrides_deleted == 1
        assert service.override_repo.get_by_line_id(lines["salary"].id) == []

    def test_duplicate_deep_copies_lines_and_overrides(self, session):
        service = ForecastService(session)
        profile = _make_profile(service)
        lines = _add_nyuad_lines(service, profile.id)
        service.add_override(lines["salary"].id, 2, Decimal("13000"))

        dup = service.duplicate_profile(profile.id, "NYUAD variant")

        assert dup.id != profile.id
        assert dup.name == "NYUAD variant"
        assert dup.horizon_months == profile.horizon_months

        orig_lines = service.line_repo.get_by_profile_id(profile.id)
        dup_lines = service.line_repo.get_by_profile_id(dup.id)
        assert len(dup_lines) == len(orig_lines) == 3
        # New line IDs.
        assert {ln.id for ln in dup_lines} & {ln.id for ln in orig_lines} == set()

        # Original untouched.
        orig_ovrs = service.override_repo.get_by_profile_id(profile.id)
        assert len(orig_ovrs) == 1

    def test_duplicate_overrides_point_to_new_line_ids(self, session):
        """Correctness-critical: copied overrides must reference NEW line IDs.

        Naive copying (overrides after lines, same loop) would make the
        dup's overrides point at the source profile's lines.
        """
        service = ForecastService(session)
        profile = _make_profile(service)
        lines = _add_nyuad_lines(service, profile.id)
        orig_ovr = service.add_override(lines["salary"].id, 2, Decimal("13000"))

        dup = service.duplicate_profile(profile.id, "variant")
        dup_lines = service.line_repo.get_by_profile_id(dup.id)
        dup_line_ids = {line.id for line in dup_lines}

        dup_ovrs = service.override_repo.get_by_profile_id(dup.id)
        assert len(dup_ovrs) == 1
        dup_ovr = dup_ovrs[0]
        assert dup_ovr.id != orig_ovr.id
        assert dup_ovr.line_id in dup_line_ids
        assert dup_ovr.line_id != orig_ovr.line_id
        assert dup_ovr.amount == orig_ovr.amount
        assert dup_ovr.month_offset == orig_ovr.month_offset

    def test_delete_profile_cascades_lines_and_overrides(self, session):
        service = ForecastService(session)
        profile = _make_profile(service)
        lines = _add_nyuad_lines(service, profile.id)
        service.add_override(lines["salary"].id, 2, Decimal("13000"))
        session.commit()   # force the cascade to go via the DB

        service.delete_profile(profile.id)
        session.commit()

        assert service.profile_repo.get_by_id(profile.id) is None
        assert service.line_repo.get_by_profile_id(profile.id) == []
        assert service.override_repo.get_by_profile_id(profile.id) == []


# ---------------------------------------------------------------------------
# Line CRUD & validation
# ---------------------------------------------------------------------------


class TestLineCRUD:
    def test_add_valid(self, session):
        service = ForecastService(session)
        profile = _make_profile(service)

        line = service.add_line(
            profile.id, "Salary", "inflow", Decimal("10000"), 0, 6
        )
        assert line.profile_id == profile.id
        assert line.kind == "inflow"
        assert line.amount == Decimal("10000")

    def test_add_rejects_unknown_profile(self, session):
        service = ForecastService(session)
        with pytest.raises(ValueError, match="profile 999 not found"):
            service.add_line(999, "X", "inflow", Decimal("1"), 0, 0)

    def test_add_rejects_blank_label(self, session):
        service = ForecastService(session)
        profile = _make_profile(service)
        with pytest.raises(ValueError, match="label cannot be empty"):
            service.add_line(profile.id, "   ", "inflow", Decimal("1"), 0, 0)

    def test_add_rejects_invalid_kind(self, session):
        service = ForecastService(session)
        profile = _make_profile(service)
        with pytest.raises(ValueError, match="Invalid kind"):
            service.add_line(profile.id, "X", "maybe", Decimal("1"), 0, 0)

    def test_add_rejects_negative_amount(self, session):
        service = ForecastService(session)
        profile = _make_profile(service)
        with pytest.raises(ValueError, match="amount must be >= 0"):
            service.add_line(profile.id, "X", "outflow", Decimal("-1"), 0, 0)

    def test_add_rejects_amount_ceiling(self, session):
        service = ForecastService(session)
        profile = _make_profile(service)
        with pytest.raises(ValueError, match="amount must be <"):
            service.add_line(
                profile.id, "X", "outflow", Decimal("1000000000"), 0, 0
            )

    def test_add_rejects_end_before_start(self, session):
        service = ForecastService(session)
        profile = _make_profile(service)
        with pytest.raises(ValueError, match="end_month_offset must be >="):
            service.add_line(profile.id, "X", "inflow", Decimal("1"), 3, 1)

    def test_add_rejects_end_equal_horizon(self, session):
        service = ForecastService(session)
        profile = _make_profile(service, horizon_months=7)
        with pytest.raises(ValueError, match=r"must be < horizon_months"):
            service.add_line(profile.id, "X", "inflow", Decimal("1"), 0, 7)

    def test_update_window_shrink_deletes_overrides(self, session):
        service = ForecastService(session)
        profile = _make_profile(service)
        line = service.add_line(
            profile.id, "Salary", "inflow", Decimal("10000"), 0, 6
        )
        service.add_override(line.id, 2, Decimal("13000"))
        service.add_override(line.id, 5, Decimal("11000"))

        result = service.update_line(line.id, end_month_offset=3)

        assert result.overrides_deleted == 1  # month 5 dropped; month 2 survives
        remaining = service.override_repo.get_by_line_id(line.id)
        assert len(remaining) == 1
        assert remaining[0].month_offset == 2

    def test_reorder(self, session):
        service = ForecastService(session)
        profile = _make_profile(service)
        line = service.add_line(
            profile.id, "X", "inflow", Decimal("1"), 0, 0, sort_order=0
        )
        updated = service.reorder_line(line.id, 5)
        assert updated.sort_order == 5

    def test_delete_line_cascades_overrides(self, session):
        service = ForecastService(session)
        profile = _make_profile(service)
        line = service.add_line(
            profile.id, "X", "inflow", Decimal("1"), 0, 6
        )
        service.add_override(line.id, 2, Decimal("2"))

        service.delete_line(line.id)

        assert service.line_repo.get_by_id(line.id) is None
        assert service.override_repo.get_by_line_id(line.id) == []


# ---------------------------------------------------------------------------
# Override CRUD & validation
# ---------------------------------------------------------------------------


class TestOverrideCRUD:
    def test_add_valid(self, session):
        service = ForecastService(session)
        profile = _make_profile(service)
        line = service.add_line(
            profile.id, "Salary", "inflow", Decimal("10000"), 0, 6
        )

        ovr = service.add_override(line.id, 2, Decimal("13000"))

        assert ovr.line_id == line.id
        assert ovr.amount == Decimal("13000")

    def test_add_rejects_unknown_line(self, session):
        service = ForecastService(session)
        with pytest.raises(ValueError, match="line 999 not found"):
            service.add_override(999, 0, Decimal("1"))

    def test_add_rejects_outside_window(self, session):
        service = ForecastService(session)
        profile = _make_profile(service)
        line = service.add_line(
            profile.id, "X", "outflow", Decimal("100"), 2, 4
        )
        with pytest.raises(ValueError, match="within line window"):
            service.add_override(line.id, 0, Decimal("1"))
        with pytest.raises(ValueError, match="within line window"):
            service.add_override(line.id, 5, Decimal("1"))

    def test_add_duplicate_raises_valueerror_not_integrityerror(self, session):
        service = ForecastService(session)
        profile = _make_profile(service)
        line = service.add_line(
            profile.id, "X", "outflow", Decimal("100"), 0, 6
        )
        service.add_override(line.id, 3, Decimal("150"))

        with pytest.raises(ValueError, match="Override already exists"):
            service.add_override(line.id, 3, Decimal("200"))

        # Session is still usable after the friendly ValueError.
        fresh = service.override_repo.get_by_line_and_month(line.id, 3)
        assert fresh is not None
        assert fresh.amount == Decimal("150")

    def test_update_amount(self, session):
        service = ForecastService(session)
        profile = _make_profile(service)
        line = service.add_line(
            profile.id, "X", "outflow", Decimal("100"), 0, 6
        )
        ovr = service.add_override(line.id, 2, Decimal("150"))

        service.update_override(ovr.id, amount=Decimal("175"))
        assert ovr.amount == Decimal("175")

    def test_delete_does_not_affect_line(self, session):
        service = ForecastService(session)
        profile = _make_profile(service)
        line = service.add_line(
            profile.id, "X", "outflow", Decimal("100"), 0, 6
        )
        ovr = service.add_override(line.id, 2, Decimal("150"))

        service.delete_override(ovr.id)

        assert service.override_repo.get_by_id(ovr.id) is None
        assert service.line_repo.get_by_id(line.id) is not None


# ---------------------------------------------------------------------------
# get_projection
# ---------------------------------------------------------------------------


class TestGetProjection:
    def test_empty_profile_flat_curve(self, session):
        service = ForecastService(session)
        profile = _make_profile(service)
        proj = service.get_projection(profile.id)

        assert len(proj.months) == 7
        assert all(m.closing_balance == Decimal("5000") for m in proj.months)
        assert proj.ending_balance == Decimal("5000")

    def test_nyuad_via_service_matches_hand_computed(self, session):
        """Mirrors Iteration 2's engine integration test, but builds data via service.

        Expected: ending_balance = 44,400 (see engine test docstring).
        """
        service = ForecastService(session)
        profile = _make_profile(service)
        lines = _add_nyuad_lines(service, profile.id)
        service.add_override(lines["salary"].id, 2, Decimal("13000"))

        proj = service.get_projection(profile.id)

        assert proj.ending_balance == Decimal("44400")
        assert proj.total_inflow == Decimal("73000")
        assert proj.total_outflow == Decimal("33600")
        assert proj.deficit_months == 0

    def test_unknown_profile_raises(self, session):
        service = ForecastService(session)
        with pytest.raises(ValueError, match="profile 999 not found"):
            service.get_projection(999)


# ---------------------------------------------------------------------------
# export_profile_to_dict
# ---------------------------------------------------------------------------


class TestExport:
    def test_shape_matches_spec(self, session):
        service = ForecastService(session)
        profile = _make_profile(service)
        lines = _add_nyuad_lines(service, profile.id)
        service.add_override(lines["salary"].id, 2, Decimal("13000"))

        payload = service.export_profile_to_dict(profile.id)

        assert set(payload.keys()) == {"profile", "lines", "projection"}
        assert payload["profile"]["name"] == "NYUAD RA"
        assert payload["profile"]["currency"] == "AED"
        assert payload["profile"]["start_date"] == "2026-06-01"
        assert payload["profile"]["opening_balance"] == "5000.00"

        assert len(payload["lines"]) == 3
        salary_line = payload["lines"][0]
        assert salary_line["amount"] == "10000.00"
        assert len(salary_line["overrides"]) == 1
        assert salary_line["overrides"][0]["amount"] == "13000.00"

        proj = payload["projection"]
        assert proj["ending_balance"] == "44400.00"
        assert proj["total_inflow"] == "73000.00"
        assert len(proj["months"]) == 7

    def test_decimals_always_two_places(self, session):
        """Every decimal in the export is quantized to exactly 2dp."""
        service = ForecastService(session)
        profile = _make_profile(service)
        # Use inputs whose scale varies; still should export as X.XX.
        service.add_line(profile.id, "Odd", "inflow", Decimal("7"), 0, 6)

        payload = service.export_profile_to_dict(profile.id)

        # Opening balance "5000.00" (not "5000"); line amount "7.00".
        assert payload["profile"]["opening_balance"] == "5000.00"
        assert payload["lines"][0]["amount"] == "7.00"
        # Every month closing also 2dp.
        for m in payload["projection"]["months"]:
            for suffix in ("opening_balance", "closing_balance", "net"):
                # All values like "5000.00", "5007.00", ...
                assert "." in m[suffix] and m[suffix].split(".")[1] == "00", (
                    f"{suffix}={m[suffix]}"
                )

    def test_roundtrip_through_json(self, session):
        service = ForecastService(session)
        profile = _make_profile(service)
        _add_nyuad_lines(service, profile.id)

        payload = service.export_profile_to_dict(profile.id)
        blob = json.dumps(payload)  # no non-serialisable types
        reloaded = json.loads(blob)
        assert reloaded["projection"]["ending_balance"] == payload["projection"][
            "ending_balance"
        ]

    def test_line_contributions_keys_are_strings(self, session):
        """line_contributions is keyed by str(line_id) for JSON compatibility."""
        service = ForecastService(session)
        profile = _make_profile(service)
        lines = _add_nyuad_lines(service, profile.id)

        payload = service.export_profile_to_dict(profile.id)

        month0 = payload["projection"]["months"][0]
        assert str(lines["salary"].id) in month0["line_contributions"]
        # Proves we can round-trip via JSON (which would reject int keys).
        json.dumps(month0["line_contributions"])

    def test_unknown_profile_raises(self, session):
        service = ForecastService(session)
        with pytest.raises(ValueError, match="profile 999 not found"):
            service.export_profile_to_dict(999)
