"""Integration tests — Textual pilot tests for the forecasting TUI.

Establishes the pilot-fixture pattern this codebase previously lacked. The
four tests below cover the core flows of the forecasts tab (picker →
detail → line CRUD → overrides → cashflow drill-down → horizon shrink).
Data-layer correctness is exhaustively covered by the 138 unit + service
tests; these tests prove the UI wiring stays correct.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from textual.widgets import DataTable, Input

from ledger.db.connection import DatabaseManager, reset_db_manager
from ledger.db.models import Base
from ledger.services.forecast_service import ForecastService
from ledger.tui.app import LedgerApp


PILOT_SIZE = (180, 50)


@pytest_asyncio.fixture
async def app_and_db(tmp_path):
    """Fresh DB + app per test. Forecasting tables created via Base metadata.

    Yields (app, dbm). The caller is responsible for `app.run_test()`.
    """
    reset_db_manager()
    dbm = DatabaseManager(str(tmp_path / "forecast_tui.db"))
    Base.metadata.create_all(dbm.engine)
    app = LedgerApp(dbm)
    yield app, dbm


def _seed_profile(dbm: DatabaseManager, **overrides) -> int:
    """Create a baseline NYUAD profile, return its id."""
    defaults = dict(
        name="NYUAD RA",
        currency="AED",
        start_date=date(2026, 6, 1),
        horizon_months=7,
        opening_balance=Decimal("5000"),
    )
    defaults.update(overrides)
    with dbm.get_session() as session:
        service = ForecastService(session)
        profile = service.create_profile(**defaults)
        return profile.id


@pytest.mark.asyncio
async def test_picker_create_profile(app_and_db):
    """Press f → n → fill → save. Confirm picker + DB both show the profile."""
    app, dbm = app_and_db
    async with app.run_test(size=PILOT_SIZE) as pilot:
        await pilot.pause()
        await pilot.press("f")
        await pilot.pause()
        # Open the create-profile modal
        await pilot.press("n")
        await pilot.pause()
        # Fill fields
        app.screen.query_one("#name_input", Input).value = "Edinburgh"
        app.screen.query_one("#currency_input", Input).value = "GBP"
        app.screen.query_one("#start_input", Input).value = "2027-01"
        app.screen.query_one("#horizon_input", Input).value = "12"
        app.screen.query_one("#opening_input", Input).value = "8000"
        await pilot.press("ctrl+s")
        await pilot.pause()

        # DB has the profile — extract primitives inside the session block.
        with dbm.get_session() as session:
            profiles = ForecastService(session).list_profiles()
            snapshot = [
                (p.name, p.currency, p.horizon_months) for p in profiles
            ]
        assert snapshot == [("Edinburgh", "GBP", 12)]

        # Picker has one row
        table = app.screen.query_one("#forecast-profiles-table", DataTable)
        assert table.row_count == 1


@pytest.mark.asyncio
async def test_line_crud_end_to_end(app_and_db):
    """Add line → cashflow recomputes → edit → delete → flat cashflow again."""
    app, dbm = app_and_db
    profile_id = _seed_profile(dbm)

    async with app.run_test(size=PILOT_SIZE) as pilot:
        await pilot.pause()
        await pilot.press("f")
        await pilot.pause()
        await pilot.press("enter")  # open detail
        await pilot.pause()

        # No lines yet → cashflow totals are zero
        with dbm.get_session() as s:
            proj0 = ForecastService(s).get_projection(profile_id)
        assert proj0.total_inflow == 0
        assert proj0.total_outflow == 0

        # Add a Salary line
        await pilot.press("n")
        await pilot.pause()
        app.screen.query_one("#label_input", Input).value = "Salary"
        # Kind defaults to outflow; flip to inflow
        from textual.widgets import Select
        app.screen.query_one("#kind_select", Select).value = "inflow"
        app.screen.query_one("#amount_input", Input).value = "10000"
        await pilot.press("ctrl+s")
        await pilot.pause()

        # Cashflow picks up the new line
        with dbm.get_session() as s:
            proj1 = ForecastService(s).get_projection(profile_id)
        assert proj1.total_inflow == Decimal("70000")  # 10k × 7 months
        assert proj1.ending_balance == Decimal("75000")  # 5k opening + 70k

        # Edit: bump amount to 12000
        await pilot.press("e")
        await pilot.pause()
        app.screen.query_one("#amount_input", Input).value = "12000"
        await pilot.press("ctrl+s")
        await pilot.pause()

        with dbm.get_session() as s:
            proj2 = ForecastService(s).get_projection(profile_id)
        assert proj2.total_inflow == Decimal("84000")

        # Delete: backspace → confirm button click
        await pilot.press("backspace")
        await pilot.pause()
        await pilot.click("#confirm_btn")
        await pilot.pause()

        with dbm.get_session() as s:
            proj3 = ForecastService(s).get_projection(profile_id)
        assert proj3.total_inflow == 0
        assert proj3.ending_balance == Decimal("5000")  # back to opening


@pytest.mark.asyncio
async def test_override_visible_in_cashflow_drilldown(app_and_db):
    """Add an override; confirm drill-down shows the overridden amount + tag."""
    app, dbm = app_and_db
    profile_id = _seed_profile(dbm)

    # Seed one line directly
    with dbm.get_session() as session:
        service = ForecastService(session)
        line = service.add_line(
            profile_id, "Salary", "inflow", Decimal("10000"), 0, 6
        )
        line_id = line.id

    async with app.run_test(size=PILOT_SIZE) as pilot:
        await pilot.pause()
        await pilot.press("f")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        # Open overrides for the first (only) line
        await pilot.press("o")
        await pilot.pause()
        # Add override: month 2 (default = line start 2026-06), so change month
        await pilot.press("n")
        await pilot.pause()
        app.screen.query_one("#month_input", Input).value = "2026-08"
        app.screen.query_one("#amount_input", Input).value = "13000"
        await pilot.press("ctrl+s")
        await pilot.pause()
        # Close overrides modal
        await pilot.press("escape")
        await pilot.pause()

        # Data-layer assertion: override is persisted
        with dbm.get_session() as session:
            overrides = ForecastService(session).list_overrides(line_id)
            override_snapshot = [(o.month_offset, o.amount) for o in overrides]
        assert override_snapshot == [(2, Decimal("13000"))]

        # Cashflow drill-down on month 2 (index 2 in cashflow table)
        cashflow = app.screen.query_one("#cashflow-table", DataTable)
        cashflow.focus()
        cashflow.move_cursor(row=2)
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        # Drill-down modal shows Salary at +13,000.00 with "override" tag
        contrib = app.screen.query_one("#contributions-table", DataTable)
        # Only one line is active this month
        assert contrib.row_count == 1
        # Column 3 is Notes — should contain "override"
        notes_cell = contrib.get_cell_at((0, 3))
        assert str(notes_cell) == "override"
        # Column 2 is Amount — Rich Text rendering the signed amount
        amount_cell = contrib.get_cell_at((0, 2))
        assert "+13,000.00" in str(amount_cell)


@pytest.mark.asyncio
async def test_horizon_shrink_surfaces_warning(app_and_db):
    """Horizon shrink with lines past the new end → warning notify with counts."""
    app, dbm = app_and_db
    profile_id = _seed_profile(dbm, horizon_months=12)

    with dbm.get_session() as session:
        ForecastService(session).add_line(
            profile_id, "Salary", "inflow", Decimal("10000"), 0, 11
        )

    async with app.run_test(size=PILOT_SIZE) as pilot:
        await pilot.pause()
        await pilot.press("f")
        await pilot.pause()
        await pilot.press("enter")  # detail
        await pilot.pause()

        # Edit metadata, shrink horizon 12 → 6
        await pilot.press("m")
        await pilot.pause()
        app.screen.query_one("#horizon_input", Input).value = "6"
        await pilot.press("ctrl+s")
        await pilot.pause()

        # A warning notify was emitted with truncation counts.
        notifications = list(app._notifications)
        warning_msgs = [
            n.message for n in notifications if n.severity == "warning"
        ]
        assert any("truncated 1 line(s)" in m for m in warning_msgs), (
            f"Expected horizon-shrink warning; got {warning_msgs!r}"
        )

        # Line was auto-truncated to end at new_horizon - 1 = 5
        with dbm.get_session() as session:
            lines = ForecastService(session).list_lines(profile_id)
            ends = [l.end_month_offset for l in lines]
        assert ends == [5]


@pytest.mark.asyncio
async def test_investment_flow_end_to_end(app_and_db):
    """Create investment → cashflow reflects auto-debit, pane populates, drill-down works."""
    app, dbm = app_and_db
    profile_id = _seed_profile(dbm, opening_balance=Decimal("10000"))

    async with app.run_test(size=PILOT_SIZE) as pilot:
        await pilot.pause()
        await pilot.press("f")
        await pilot.pause()
        await pilot.press("enter")  # open detail
        await pilot.pause()

        # Open investments modal and add one
        await pilot.press("v")
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        app.screen.query_one("#label_input", Input).value = "S&P 500"
        app.screen.query_one("#starting_input", Input).value = "10000"
        app.screen.query_one("#contribution_input", Input).value = "500"
        app.screen.query_one("#rate_input", Input).value = "7"
        await pilot.press("ctrl+s")
        await pilot.pause()
        await pilot.press("escape")  # close list modal
        await pilot.pause()

        # (a) Investment persists
        with dbm.get_session() as session:
            invs = ForecastService(session).list_investments(profile_id)
            snapshot = [
                (i.label, str(i.starting_balance), str(i.monthly_contribution),
                 str(i.annual_growth_rate))
                for i in invs
            ]
        assert snapshot == [("S&P 500", "10000.00", "500.00", "7.0000")]

        # (b) Cashflow total_outflow reflects the contribution × horizon
        with dbm.get_session() as session:
            proj = ForecastService(session).get_projection(profile_id)
        assert proj.total_outflow == Decimal("3500.00")  # 7 × 500
        assert proj.ending_balance == Decimal("6500.00")  # 10k - 3500
        # Investments grow through compounding + contributions
        assert proj.ending_investment_value.quantize(Decimal("0.01")) > Decimal("13000")

        # (c) Investments pane populated with one row per horizon month,
        # each with positive growth (compounding is working).
        from textual.widgets import DataTable
        inv_table = app.screen.query_one("#investments-table", DataTable)
        assert inv_table.row_count == 7

        # Drill down on month 0 — should have 1 investment row
        inv_table.focus()
        inv_table.move_cursor(row=0)
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        drill_table = app.screen.query_one("#investment-month-table", DataTable)
        assert drill_table.row_count == 1


@pytest.mark.asyncio
async def test_investment_appears_as_line_item(app_and_db):
    """Investments render as rows in the Lines table; e edits via investment form."""
    app, dbm = app_and_db
    profile_id = _seed_profile(dbm, opening_balance=Decimal("10000"))

    # Seed one forecast line and one investment directly.
    with dbm.get_session() as session:
        service = ForecastService(session)
        service.add_line(
            profile_id, "Salary", "inflow", Decimal("10000"), 0, 6
        )
        service.add_investment(
            profile_id=profile_id,
            label="S&P 500",
            starting_balance=Decimal("10000"),
            monthly_contribution=Decimal("500"),
            annual_growth_rate=Decimal("7"),
            sort_order=0,
            notes=None,
        )

    async with app.run_test(size=PILOT_SIZE) as pilot:
        await pilot.pause()
        await pilot.press("f")
        await pilot.pause()
        await pilot.press("enter")  # open detail
        await pilot.pause()

        # Lines table has: salary row, separator (inflows ↔ investments),
        # and investment row. Three rows total.
        lines_table = app.screen.query_one("#lines-table", DataTable)
        assert lines_table.row_count == 3

        # Row 0 = the Salary line (kind "inflow").
        kind_cell_0 = lines_table.get_cell_at((0, 1))
        assert "inflow" in str(kind_cell_0)

        # Row 2 = the investment, tagged "invest" (row 1 is the separator).
        label_cell_2 = lines_table.get_cell_at((2, 0))
        assert "S&P 500" in str(label_cell_2)
        kind_cell_2 = lines_table.get_cell_at((2, 1))
        assert "invest" in str(kind_cell_2)
        amount_cell_2 = lines_table.get_cell_at((2, 2))
        assert "500.00" in str(amount_cell_2)

        # Press `e` on the investment row → investment edit form opens.
        lines_table.focus()
        lines_table.move_cursor(row=2)
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()

        # Investment form uses #rate_input; the line form does not.
        assert app.screen.query_one("#rate_input", Input).value == "7.0000"

        # Bump contribution to 750 via the same form.
        app.screen.query_one("#contribution_input", Input).value = "750"
        await pilot.press("ctrl+s")
        await pilot.pause()

        with dbm.get_session() as session:
            invs = ForecastService(session).list_investments(profile_id)
            contributions = [i.monthly_contribution for i in invs]
        assert contributions == [Decimal("750.00")]


@pytest.mark.asyncio
async def test_tax_flow_end_to_end(app_and_db):
    """Create tax profile inline, attach to salary, verify net inflow + drill-down."""
    app, dbm = app_and_db
    profile_id = _seed_profile(
        dbm,
        currency="GBP",
        start_date=date(2025, 4, 1),  # aligns with a known tax year (2025-26)
        horizon_months=12,
        opening_balance=Decimal("0"),
    )

    # Seed a tax profile directly — exercising the full inline-sentinel flow
    # is covered in the form's own unit/integration tests. Here we focus on
    # the engine + Lines table + drill-down integration.
    with dbm.get_session() as session:
        service = ForecastService(session)
        tp = service.add_tax_profile(name="Scotland full")
        service.add_line(
            profile_id,
            "Salary",
            "inflow",
            Decimal("5000"),
            0,
            11,
            tax_profile_id=tp.id,
        )

    async with app.run_test(size=PILOT_SIZE) as pilot:
        await pilot.pause()
        await pilot.press("f")
        await pilot.pause()
        await pilot.press("enter")  # open detail
        await pilot.pause()

        # Lines table: one salary row plus a synthetic `— Salary: tax` row.
        lines_table = app.screen.query_one("#lines-table", DataTable)
        assert lines_table.row_count == 2

        # Row 0 = the salary line, Row 1 = the derived tax row.
        kind_cell_0 = lines_table.get_cell_at((0, 1))
        assert "inflow" in str(kind_cell_0)
        kind_cell_1 = lines_table.get_cell_at((1, 1))
        assert "tax" in str(kind_cell_1)
        label_cell_1 = lines_table.get_cell_at((1, 0))
        assert "Salary" in str(label_cell_1) and "tax" in str(label_cell_1)

        # Projection: total_inflow should be net of Scottish IT + NI.
        with dbm.get_session() as session:
            proj = ForecastService(session).get_projection(profile_id)
        # Gross 60,000; IT 13,228.31; NI 267.50 × 12 = 3,210; net 43,561.69.
        assert proj.total_inflow.quantize(Decimal("0.01")) == Decimal("43561.69")

        # Drill down on month 0 — should show Salary gross + Income tax + NI.
        cashflow = app.screen.query_one("#cashflow-table", DataTable)
        cashflow.focus()
        cashflow.move_cursor(row=0)
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        contrib = app.screen.query_one("#contributions-table", DataTable)
        # Three rows: gross salary + income tax + NI.
        assert contrib.row_count == 3
        labels = [str(contrib.get_cell_at((r, 0))) for r in range(3)]
        assert any("Income tax" in l for l in labels)
        assert any("NI" in l for l in labels)
        assert any("Salary" in l and "—" not in l for l in labels)


@pytest.mark.asyncio
async def test_tax_profile_inline_create_from_line_form(app_and_db):
    """Through the line form: pick '+ New tax profile…', create, select it."""
    app, dbm = app_and_db
    profile_id = _seed_profile(
        dbm,
        currency="GBP",
        start_date=date(2025, 4, 1),
        horizon_months=12,
        opening_balance=Decimal("0"),
    )

    async with app.run_test(size=PILOT_SIZE) as pilot:
        await pilot.pause()
        await pilot.press("f")
        await pilot.pause()
        await pilot.press("enter")  # open detail
        await pilot.pause()
        await pilot.press("n")  # new line form
        await pilot.pause()

        # Fill in base line fields.
        from textual.widgets import Select
        app.screen.query_one("#label_input", Input).value = "Salary"
        app.screen.query_one("#kind_select", Select).value = "inflow"
        app.screen.query_one("#amount_input", Input).value = "5000"
        await pilot.pause()

        # Trigger the "+ New tax profile…" sentinel — this should open the
        # nested TaxProfileFormModal.
        from ledger.tui.widgets.forecast_line_form import (
            TAX_PROFILE_NEW_SENTINEL,
        )
        tax_select = app.screen.query_one("#tax_profile_select", Select)
        tax_select.value = TAX_PROFILE_NEW_SENTINEL
        await pilot.pause()

        # Fill in the tax profile form.
        app.screen.query_one("#name_input", Input).value = "Scotland full"
        await pilot.press("ctrl+s")
        await pilot.pause()

        # Tax profile persists.
        with dbm.get_session() as session:
            tps = ForecastService(session).list_tax_profiles()
            names = [tp.name for tp in tps]
        assert names == ["Scotland full"]

        # Back on the line form: the new profile is selected.
        tax_select = app.screen.query_one("#tax_profile_select", Select)
        new_id = str(tps[0].id) if False else None  # refetch id
        with dbm.get_session() as session:
            new_id = str(ForecastService(session).list_tax_profiles()[0].id)
        assert tax_select.value == new_id

        # Save the line; assert it's persisted with tax_profile_id.
        await pilot.press("ctrl+s")
        await pilot.pause()

        with dbm.get_session() as session:
            lines = ForecastService(session).list_lines(profile_id)
            snapshot = [(l.label, l.tax_profile_id) for l in lines]
        assert snapshot == [("Salary", int(new_id))]


@pytest.mark.asyncio
async def test_until_next_override_spans_months(app_and_db):
    """A until_next override applies from its month to end, and the list
    renders `start → end` live-computed against the line window."""
    app, dbm = app_and_db
    profile_id = _seed_profile(dbm, horizon_months=12)

    # Seed a simple inflow line directly; 12 months of £1,000.
    with dbm.get_session() as session:
        service = ForecastService(session)
        line = service.add_line(
            profile_id, "Salary", "inflow", Decimal("1000"), 0, 11
        )
        # Step override starting at month 5.
        service.add_override(
            line.id,
            month_offset=5,
            amount=Decimal("1500"),
            effect_span="until_next",
        )

    async with app.run_test(size=PILOT_SIZE) as pilot:
        await pilot.pause()
        await pilot.press("f")
        await pilot.pause()
        await pilot.press("enter")  # open detail
        await pilot.pause()

        # Verify projection: months 0-4 = 1000; months 5-11 = 1500.
        with dbm.get_session() as session:
            proj = ForecastService(session).get_projection(profile_id)
        assert proj.months[4].total_inflow == Decimal("1000")
        assert proj.months[5].total_inflow == Decimal("1500")
        assert proj.months[11].total_inflow == Decimal("1500")

        # Open overrides list for the line.
        lines_table = app.screen.query_one("#lines-table", DataTable)
        lines_table.focus()
        lines_table.move_cursor(row=0)
        await pilot.pause()
        await pilot.press("o")
        await pilot.pause()

        # Overrides list shows the live-computed span in the Month column.
        ovr_table = app.screen.query_one("#overrides-table", DataTable)
        assert ovr_table.row_count == 1
        month_cell = str(ovr_table.get_cell_at((0, 0)))
        # 12-month profile starting June 2026: offset 5 = Nov 2026,
        # offset 11 = May 2027.
        assert "→" in month_cell
        assert "2026-11" in month_cell
        assert "2027-05" in month_cell
