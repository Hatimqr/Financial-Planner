"""Fork 0 smoke test — visit every screen, confirm StatusFooter renders.

Verifies:
1. Every screen yields a `StatusFooter` that mounts without error.
2. The PeriodBar shows the `[P]eriods` affordance (replaces the old `+`).
3. Dynamic footer hints update on the Transactions screen when focus moves
   between the search input and the transactions table.
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
from ledger.tui.widgets.period_bar import PeriodBar
from ledger.tui.widgets.status_footer import StatusFooter


PILOT_SIZE = (200, 60)


@pytest_asyncio.fixture
async def app_and_db(tmp_path):
    reset_db_manager()
    dbm = DatabaseManager(str(tmp_path / "fork0_smoke.db"))
    Base.metadata.create_all(dbm.engine)
    app = LedgerApp(dbm)
    yield app, dbm


@pytest.mark.asyncio
async def test_every_screen_mounts_status_footer(app_and_db):
    """Each main screen must show a StatusFooter on initial render."""
    app, dbm = app_and_db
    # Seed a forecast profile so the forecast detail screen has content.
    with dbm.get_session() as session:
        ForecastService(session).create_profile(
            name="Smoke",
            currency="GBP",
            start_date=date(2027, 1, 1),
            horizon_months=3,
            opening_balance=Decimal("1000"),
        )

    screen_keys = ("d", "a", "t", "r", "b", "f", "i")
    async with app.run_test(size=PILOT_SIZE) as pilot:
        await pilot.pause()
        for key in screen_keys:
            await pilot.press(key)
            await pilot.pause()
            footers = list(app.screen.query(StatusFooter))
            assert len(footers) == 1, (
                f"Screen for {key!r} yielded {len(footers)} StatusFooters "
                f"(expected 1)"
            )


@pytest.mark.asyncio
async def test_period_bar_shows_periods_affordance(app_and_db):
    """PeriodBar render() must produce `[P]eriods` text (replaces `+`)."""
    app, _ = app_and_db
    async with app.run_test(size=PILOT_SIZE) as pilot:
        await pilot.pause()
        bar = app.screen.query_one(PeriodBar)
        rendered = bar.render().plain
        assert "[P]eriods" in rendered, f"PeriodBar render missing [P]eriods: {rendered!r}"
        assert " + " not in rendered, f"PeriodBar still shows old `+` affordance: {rendered!r}"


@pytest.mark.asyncio
async def test_transactions_hints_update_on_focus(app_and_db):
    """On Transactions, focusing the search input vs. the table swaps hints."""
    app, _ = app_and_db
    async with app.run_test(size=PILOT_SIZE) as pilot:
        await pilot.press("t")
        await pilot.pause()

        footer = app.screen.query_one("#transactions-footer", StatusFooter)

        hints_widget = footer.query_one(".status-footer-hints")

        def _hint_text() -> str:
            r = hints_widget.render()
            return getattr(r, "plain", str(r))

        # Reveal + focus the search input via Ctrl+/ (real user path).
        await pilot.press("ctrl+slash")
        await pilot.pause()
        search_hint_text = _hint_text()

        # Focus the data table
        app.screen.query_one("#transactions_table", DataTable).focus()
        await pilot.pause()
        table_hint_text = _hint_text()

        assert search_hint_text != table_hint_text, (
            f"Hint did not change between search and table focus: "
            f"search={search_hint_text!r}, table={table_hint_text!r}"
        )
        assert "Esc" in search_hint_text
        assert "ew" in table_hint_text  # default hints contain "[N]ew"
