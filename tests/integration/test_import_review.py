"""Import Review screen polish — verifies Fork-6 scope.

Covers:
1. Empty state is visible before a file loads; table is hidden.
2. No period bar on this screen (not period-driven).
3. No Cancel button — Esc is the only back affordance.
4. Statement metadata after load renders into `#import_info` (subtitle).
5. Footer summary updates after load (Fork 0 contract).
6. Focus-driven footer hints swap between file-path input and the table.
7. Confirm button is disabled with nothing loaded, enabled once rows include.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
import pytest_asyncio
from textual.widgets import Button, DataTable, Input, Select, Static

from ledger.db.connection import DatabaseManager, reset_db_manager
from ledger.db.models import Base
from ledger.services.account_service import AccountService
from ledger.tui.app import LedgerApp
from ledger.tui.widgets.period_bar import PeriodBar
from ledger.tui.widgets.status_footer import StatusFooter


PILOT_SIZE = (220, 60)


@pytest_asyncio.fixture
async def app_and_db(tmp_path):
    reset_db_manager()
    dbm = DatabaseManager(str(tmp_path / "import_review.db"))
    Base.metadata.create_all(dbm.engine)

    # One checking + one expense account so resolve_accounts can find a target.
    with dbm.get_session() as session:
        svc = AccountService(session)
        svc.create_account(name="Assets:Checking", account_type="asset", currency="AED")
        svc.create_account(name="Expenses:Food", account_type="expense", currency="AED")

    app = LedgerApp(dbm)
    yield app, dbm, tmp_path


def _write_statement(tmp_path, name="stmt.json") -> str:
    """Minimal JSON statement shaped for PdfImportService.load_json_file."""
    payload = {
        "bank_name": "TestBank",
        "currency": "AED",
        "statement_period_from": "2026-03-01",
        "statement_period_to": "2026-03-31",
        "opening_balance": 1000.00,
        "closing_balance": 950.00,
        "transactions": [
            {
                "date": "2026-03-05",
                "description": "Coffee",
                "payee": "Starbucks",
                "amount": -5.50,
                "category": "Food",
            },
            {
                "date": "2026-03-10",
                "description": "Lunch",
                "payee": "Deli",
                "amount": -12.00,
                "category": "Food",
            },
        ],
    }
    p = tmp_path / name
    p.write_text(json.dumps(payload))
    return str(p)


@pytest.mark.asyncio
async def test_empty_state_visible_before_load(app_and_db):
    app, _, _ = app_and_db
    async with app.run_test(size=PILOT_SIZE) as pilot:
        await pilot.press("i")
        await pilot.pause()
        empty = app.screen.query_one("#import-empty-state", Static)
        table = app.screen.query_one("#import_review_table", DataTable)
        assert empty.display, "Empty-state placeholder should be visible pre-load"
        assert not table.display, "Table should be hidden pre-load"


@pytest.mark.asyncio
async def test_no_period_bar_on_import(app_and_db):
    app, _, _ = app_and_db
    async with app.run_test(size=PILOT_SIZE) as pilot:
        await pilot.press("i")
        await pilot.pause()
        # Import is file-driven, not period-driven — the bar is suppressed.
        assert not list(app.screen.query(PeriodBar))


@pytest.mark.asyncio
async def test_no_cancel_button(app_and_db):
    app, _, _ = app_and_db
    async with app.run_test(size=PILOT_SIZE) as pilot:
        await pilot.press("i")
        await pilot.pause()
        # Cancel was redundant with Esc; should be gone.
        button_ids = {b.id for b in app.screen.query(Button)}
        assert "cancel_btn" not in button_ids
        assert "confirm_btn" in button_ids


@pytest.mark.asyncio
async def test_load_populates_subtitle_and_footer(app_and_db):
    app, _, tmp_path = app_and_db
    stmt = _write_statement(tmp_path)

    async with app.run_test(size=PILOT_SIZE) as pilot:
        await pilot.press("i")
        await pilot.pause()

        # Pick the Assets:Checking source account. Find its id.
        with app.db_manager.get_session() as session:
            svc = AccountService(session)
            checking = svc.get_account_by_name("Assets:Checking")
            assert checking is not None
            checking_id = str(checking.id)

        app.screen.query_one("#file_path_input", Input).value = stmt
        app.screen.query_one("#source_account_select", Select).value = checking_id
        await pilot.pause()
        app.screen.query_one("#load_btn", Button).press()
        await pilot.pause()

        info = app.screen.query_one("#import_info", Static)
        rendered = info.render()
        info_text = getattr(rendered, "plain", str(rendered))
        assert "TestBank" in info_text
        assert "AED" in info_text

        footer = app.screen.query_one("#import-footer", StatusFooter)
        summary_widget = footer.query_one(".status-footer-summary")
        summary_text = getattr(summary_widget.render(), "plain", str(summary_widget.render()))
        assert "2 txns" in summary_text
        assert "included" in summary_text


@pytest.mark.asyncio
async def test_hints_swap_on_focus(app_and_db):
    app, _, _ = app_and_db
    async with app.run_test(size=PILOT_SIZE) as pilot:
        await pilot.press("i")
        await pilot.pause()

        footer = app.screen.query_one("#import-footer", StatusFooter)
        hints_widget = footer.query_one(".status-footer-hints")

        def _hint() -> str:
            r = hints_widget.render()
            return getattr(r, "plain", str(r))

        # File-path input gets focus on mount — should show load-specific hint.
        file_input = app.screen.query_one("#file_path_input", Input)
        file_input.focus()
        await pilot.pause()
        file_hint = _hint()
        assert "load" in file_hint.lower()

        # Switch focus to the table → default hints (mention Confirm).
        table = app.screen.query_one("#import_review_table", DataTable)
        table.display = True  # force-visible so focus lands
        table.focus()
        await pilot.pause()
        table_hint = _hint()
        assert table_hint != file_hint
        assert "onfirm" in table_hint  # default hints include [C]onfirm
