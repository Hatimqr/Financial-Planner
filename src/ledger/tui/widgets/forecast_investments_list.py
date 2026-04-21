"""Investments list modal — list, add, edit, delete investments for a profile."""

from __future__ import annotations

from decimal import Decimal

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static

from ledger.db.connection import DatabaseManager
from ledger.services.forecast_service import ForecastService
from ledger.tui.widgets.confirm_dialog import ConfirmDialog
from ledger.tui.widgets.forecast_investment_form import InvestmentFormModal
from ledger.tui.widgets.forecast_investment_overrides_list import (
    InvestmentOverridesListModal,
)


class InvestmentsListModal(ModalScreen):
    """Modal listing a profile's investments with CRUD actions.

    Nests `InvestmentFormModal` and `ConfirmDialog` via `push_screen`.
    Mirrors `OverridesListModal` in structure.
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("n", "new_investment", "New"),
        Binding("e", "edit_investment", "Edit"),
        Binding("backspace", "delete_investment", "Delete"),
        Binding("o", "open_overrides", "Overrides"),
    ]

    def __init__(self, db_manager: DatabaseManager, profile_id: int):
        super().__init__()
        self.db_manager = db_manager
        self.profile_id = profile_id
        self._investment_ids: list[int] = []
        # Any CRUD change makes the parent detail refresh on dismiss.
        self._changed: bool = False

    def compose(self) -> ComposeResult:
        yield Container(
            Static("Investments", classes="modal-title"),
            Static("", id="investments-empty", classes="placeholder-notice"),
            DataTable(id="investments-list-table", zebra_stripes=True),
            Static(
                "n new · e edit · o overrides · ⌫ delete · Enter edit · Esc close",
                classes="forecast-summary",
            ),
            Horizontal(
                Button("Close [Esc]", variant="default", id="close_btn"),
                classes="button-row",
            ),
            classes="modal investments-list-modal",
        )

    def on_mount(self) -> None:
        table = self.query_one("#investments-list-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Label", "Starting", "Monthly", "Rate", "Overrides", "Ending")
        self.load_investments()

    def load_investments(self) -> None:
        table = self.query_one("#investments-list-table", DataTable)
        empty = self.query_one("#investments-empty", Static)

        prev_cursor = table.cursor_row
        table.clear()
        self._investment_ids = []

        try:
            with self.db_manager.get_session() as session:
                service = ForecastService(session)
                investments = service.list_investments(self.profile_id)
                # Use projection for live ending balances per investment.
                proj = service.get_projection(self.profile_id)
                summary_by_id = {
                    s.investment_id: s
                    for s in proj.investment_summaries
                }

                for inv in investments:
                    summary = summary_by_id.get(inv.id)
                    ending = (
                        summary.ending_balance
                        if summary is not None
                        else inv.starting_balance
                    )
                    override_count = (
                        summary.override_count if summary is not None else 0
                    )
                    ovr_display = (
                        "—" if override_count == 0 else str(override_count)
                    )
                    table.add_row(
                        inv.label[:32],
                        Text(format(inv.starting_balance, ",.2f"), justify="right"),
                        Text(
                            format(inv.monthly_contribution, ",.2f"),
                            justify="right",
                        ),
                        Text(
                            f"{format(inv.annual_growth_rate, 'f')}%",
                            justify="right",
                        ),
                        Text(ovr_display, justify="right"),
                        Text(format(ending.quantize(Decimal('0.01')), ",.2f"), justify="right"),
                    )
                    self._investment_ids.append(inv.id)
        except ValueError:
            self.notify("Profile no longer exists", severity="warning")
            self.action_close()
            return
        except Exception as e:
            self.notify(f"Error loading investments: {e}", severity="error")
            return

        count = len(self._investment_ids)
        if count == 0:
            empty.update(
                "No investments yet. Press [bold]n[/] to add one."
            )
            empty.display = True
            table.display = False
        else:
            empty.display = False
            table.display = True
            if prev_cursor is not None and table.row_count > 0:
                table.move_cursor(
                    row=min(prev_cursor, table.row_count - 1)
                )
            if not table.has_focus:
                table.focus()

    def _selected_investment_id(self) -> int | None:
        table = self.query_one("#investments-list-table", DataTable)
        if (
            table.cursor_row is not None
            and 0 <= table.cursor_row < len(self._investment_ids)
        ):
            return self._investment_ids[table.cursor_row]
        return None

    def action_close(self) -> None:
        self.dismiss(self._changed)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close_btn":
            self.action_close()

    def action_new_investment(self) -> None:
        def on_saved(result):
            if result is None:
                return
            self._changed = True
            self.load_investments()

        try:
            modal = InvestmentFormModal(self.db_manager, self.profile_id)
        except ValueError:
            self.notify("Profile no longer exists", severity="warning")
            self.action_close()
            return
        self.app.push_screen(modal, on_saved)

    def action_edit_investment(self) -> None:
        investment_id = self._selected_investment_id()
        if investment_id is None:
            self.notify("No investment selected", severity="warning")
            return

        try:
            modal = InvestmentFormModal(
                self.db_manager, self.profile_id, investment_id=investment_id
            )
        except ValueError:
            self.notify("Investment no longer exists", severity="warning")
            self._changed = True
            self.load_investments()
            return

        def on_saved(result):
            if result is None:
                return
            if result == InvestmentFormModal.DELETE_SENTINEL:
                self._confirm_delete(investment_id)
                return
            self._changed = True
            self.load_investments()

        self.app.push_screen(modal, on_saved)

    def action_open_overrides(self) -> None:
        investment_id = self._selected_investment_id()
        if investment_id is None:
            self.notify("No investment selected", severity="warning")
            return

        def on_closed(changed: bool | None) -> None:
            if changed:
                self._changed = True
                self.load_investments()

        try:
            modal = InvestmentOverridesListModal(
                self.db_manager, investment_id
            )
        except ValueError:
            self.notify("Investment no longer exists", severity="warning")
            self._changed = True
            self.load_investments()
            return
        self.app.push_screen(modal, on_closed)

    def action_delete_investment(self) -> None:
        investment_id = self._selected_investment_id()
        if investment_id is None:
            self.notify("No investment selected", severity="warning")
            return
        self._confirm_delete(investment_id)

    def _confirm_delete(self, investment_id: int) -> None:
        def on_confirmed(confirmed: bool) -> None:
            if not confirmed:
                return
            try:
                with self.db_manager.get_session() as session:
                    service = ForecastService(session)
                    service.delete_investment(investment_id)
            except ValueError:
                self.notify(
                    "Investment no longer exists", severity="warning"
                )
            except Exception as e:
                self.notify(
                    f"Error deleting investment: {e}", severity="error"
                )
                return
            self._changed = True
            self.load_investments()

        self.app.push_screen(
            ConfirmDialog("Delete this investment?"),
            on_confirmed,
        )

    def on_data_table_row_selected(
        self, event: DataTable.RowSelected
    ) -> None:
        if event.data_table.id == "investments-list-table":
            self.action_edit_investment()
