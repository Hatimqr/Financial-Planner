"""Investment overrides list modal — list/manage an investment's overrides."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static

from ledger.db.connection import DatabaseManager
from ledger.services.forecast_service import ForecastService
from ledger.tui.widgets._forecast_month import offset_to_ym_label
from ledger.tui.widgets.confirm_dialog import ConfirmDialog
from ledger.tui.widgets.forecast_investment_override_form import (
    InvestmentOverrideFormModal,
)


class InvestmentOverridesListModal(ModalScreen):
    """Modal listing an investment's contribution overrides with CRUD actions.

    Mirrors :class:`OverridesListModal` but scoped to an investment instead
    of a line. An investment has no per-line window, so the visible
    "end of span" for ``until_next`` overrides is bounded by the next
    override (any type) on the same investment or the profile horizon.
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("n", "new_override", "New"),
        Binding("e", "edit_override", "Edit"),
        Binding("backspace", "delete_override", "Delete"),
    ]

    def __init__(self, db_manager: DatabaseManager, investment_id: int):
        super().__init__()
        self.db_manager = db_manager
        self.investment_id = investment_id
        self._override_ids: list[int] = []
        self._changed: bool = False

        with db_manager.get_session() as session:
            service = ForecastService(session)
            inv = service.investment_repo.get_by_id(investment_id)
            if inv is None:
                raise ValueError(
                    f"Forecast investment {investment_id} not found"
                )
            profile = service.get_profile(inv.profile_id)
            if profile is None:
                raise ValueError(
                    f"Forecast profile {inv.profile_id} not found"
                )
            self._inv_label = inv.label
            self._inv_base_contribution = format(inv.monthly_contribution, ",.2f")
            self._horizon_last_offset = profile.horizon_months - 1
            self._profile_start_year = profile.start_date.year
            self._profile_start_month = profile.start_date.month

    def compose(self) -> ComposeResult:
        yield Container(
            Static(
                f'Contribution overrides for "{self._inv_label}"',
                classes="modal-title",
            ),
            Static(
                f"Base contribution: {self._inv_base_contribution}",
                classes="modal-subhint",
            ),
            Static("", id="overrides-empty", classes="placeholder-notice"),
            DataTable(id="inv-overrides-table", zebra_stripes=True),
            Static(
                "n new · e edit · ⌫ delete · Enter edit · Esc close",
                classes="forecast-summary",
            ),
            Horizontal(
                Button("Close [Esc]", variant="default", id="close_btn"),
                classes="button-row",
            ),
            classes="modal overrides-list-modal",
        )

    def on_mount(self) -> None:
        table = self.query_one("#inv-overrides-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Month", "Amount", "Notes")
        self.load_overrides()
        if table.row_count > 0:
            table.focus()

    def load_overrides(self) -> None:
        table = self.query_one("#inv-overrides-table", DataTable)
        empty = self.query_one("#overrides-empty", Static)

        prev_cursor = table.cursor_row
        table.clear()
        self._override_ids = []

        try:
            with self.db_manager.get_session() as session:
                service = ForecastService(session)
                overrides = service.list_investment_overrides(self.investment_id)

                all_starts = sorted(o.month_offset for o in overrides)

                for o in overrides:
                    start_label = offset_to_ym_label(
                        self._profile_start_year,
                        self._profile_start_month,
                        o.month_offset,
                    )
                    if o.effect_span == "until_next":
                        later = [s for s in all_starts if s > o.month_offset]
                        end_offset = (
                            (later[0] - 1)
                            if later
                            else self._horizon_last_offset
                        )
                        end_label = offset_to_ym_label(
                            self._profile_start_year,
                            self._profile_start_month,
                            end_offset,
                        )
                        month_cell = f"{start_label} → {end_label}"
                    else:
                        month_cell = start_label
                    table.add_row(
                        month_cell,
                        format(o.amount, ",.2f"),
                        (o.notes or "")[:40],
                    )
                    self._override_ids.append(o.id)
        except ValueError:
            self.notify("Investment no longer exists", severity="warning")
            self.action_close()
            return
        except Exception as e:
            self.notify(f"Error loading overrides: {e}", severity="error")
            return

        count = len(self._override_ids)
        if count == 0:
            empty.update(
                'No overrides yet. Press [bold]n[/] to add one — overrides '
                "replace the monthly contribution for a specific month."
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

    def _selected_override_id(self) -> int | None:
        table = self.query_one("#inv-overrides-table", DataTable)
        if (
            table.cursor_row is not None
            and 0 <= table.cursor_row < len(self._override_ids)
        ):
            return self._override_ids[table.cursor_row]
        return None

    def action_close(self) -> None:
        self.dismiss(self._changed)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close_btn":
            self.action_close()

    def action_new_override(self) -> None:
        def on_saved(result):
            if result is None:
                return
            self._changed = True
            self.load_overrides()

        try:
            modal = InvestmentOverrideFormModal(
                self.db_manager, self.investment_id
            )
        except ValueError:
            self.notify("Investment no longer exists", severity="warning")
            self.action_close()
            return
        self.app.push_screen(modal, on_saved)

    def action_edit_override(self) -> None:
        override_id = self._selected_override_id()
        if override_id is None:
            self.notify("No override selected", severity="warning")
            return

        try:
            modal = InvestmentOverrideFormModal(
                self.db_manager,
                self.investment_id,
                override_id=override_id,
            )
        except ValueError:
            self.notify("Override no longer exists", severity="warning")
            self._changed = True
            self.load_overrides()
            return

        def on_saved(result):
            if result is None:
                return
            if result == InvestmentOverrideFormModal.DELETE_SENTINEL:
                self._confirm_delete(override_id)
                return
            self._changed = True
            self.load_overrides()

        self.app.push_screen(modal, on_saved)

    def action_delete_override(self) -> None:
        override_id = self._selected_override_id()
        if override_id is None:
            self.notify("No override selected", severity="warning")
            return
        self._confirm_delete(override_id)

    def _confirm_delete(self, override_id: int) -> None:
        def on_confirmed(confirmed: bool) -> None:
            if not confirmed:
                return
            try:
                with self.db_manager.get_session() as session:
                    service = ForecastService(session)
                    service.delete_investment_override(override_id)
            except ValueError:
                self.notify(
                    "Override no longer exists", severity="warning"
                )
            except Exception as e:
                self.notify(
                    f"Error deleting override: {e}", severity="error"
                )
                return
            self._changed = True
            self.load_overrides()

        self.app.push_screen(
            ConfirmDialog("Delete this override?"),
            on_confirmed,
        )

    def on_data_table_row_selected(
        self, event: DataTable.RowSelected
    ) -> None:
        if event.data_table.id == "inv-overrides-table":
            self.action_edit_override()
