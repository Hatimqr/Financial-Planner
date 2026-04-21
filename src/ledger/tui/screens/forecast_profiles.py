"""Forecast profiles picker screen — list + CRUD for profiles."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import DataTable, Static

from ledger.db.connection import DatabaseManager
from ledger.services.forecast_service import ForecastService
from ledger.tui.widgets._forecast_month import offset_to_ym_label
from ledger.tui.widgets.app_header import AppHeader
from ledger.tui.widgets.confirm_dialog import ConfirmDialog
from ledger.tui.widgets.forecast_profile_duplicate import DuplicateProfileModal
from ledger.tui.widgets.forecast_profile_form import (
    ForecastProfileFormModal,
    ProfileFormResult,
)
from ledger.tui.widgets.status_footer import StatusFooter


class ForecastProfilesScreen(Screen):
    """Top-level screen listing forecast profiles with CRUD actions."""

    BINDINGS = [
        Binding("n", "new_profile", "New"),
        Binding("e", "edit_profile", "Edit"),
        Binding("c", "duplicate_profile", "Duplicate"),
        Binding("backspace", "delete_profile", "Delete"),
        Binding("enter", "open_profile", "Open"),
    ]

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager
        self._profile_ids: list[int] = []

    def compose(self) -> ComposeResult:
        yield AppHeader("Forecasts", show_period_bar=False)
        yield Container(
            Static("", id="forecast-profiles-subtitle", classes="screen-subtitle"),
            DataTable(id="forecast-profiles-table", zebra_stripes=True),
            Static("", id="forecast-profiles-empty", classes="placeholder-notice"),
            id="forecast-profiles-container",
        )
        yield StatusFooter(id="forecast-profiles-footer")

    def on_mount(self) -> None:
        table = self.query_one("#forecast-profiles-table", DataTable)
        table.cursor_type = "row"
        table.add_column("Name", key="name", width=30)
        table.add_column("Currency", key="currency", width=10)
        table.add_column("Start", key="start", width=10)
        table.add_column("End", key="end", width=10)
        table.add_column("Lines", key="lines", width=7)
        table.add_column("Opening", key="opening", width=14)
        self.load_profiles()
        table.focus()

    def load_profiles(self) -> None:
        """Load forecast profiles from DB and populate the table."""
        table = self.query_one("#forecast-profiles-table", DataTable)
        empty = self.query_one("#forecast-profiles-empty", Static)
        subtitle = self.query_one("#forecast-profiles-subtitle", Static)
        footer = self.query_one("#forecast-profiles-footer", StatusFooter)

        table.clear()
        self._profile_ids = []
        currencies: set[str] = set()
        horizons: list[int] = []

        try:
            with self.db_manager.get_session() as session:
                service = ForecastService(session)
                profiles = service.list_profiles()

                for p in profiles:
                    end_label = offset_to_ym_label(
                        p.start_date.year,
                        p.start_date.month,
                        max(p.horizon_months - 1, 0),
                    )
                    line_count = len(service.list_lines(p.id))
                    table.add_row(
                        p.name,
                        p.currency,
                        p.start_date.strftime("%Y-%m"),
                        end_label,
                        str(line_count),
                        format(p.opening_balance, ",.2f"),
                    )
                    self._profile_ids.append(p.id)
                    currencies.add(p.currency)
                    horizons.append(p.horizon_months)
        except Exception as e:
            self.notify(f"Error loading forecast profiles: {e}", severity="error")
            return

        count = len(self._profile_ids)
        if count == 0:
            subtitle.update("")
            empty.update("No forecast profiles yet. Press [bold]n[/] to create one.")
            empty.display = True
            table.display = False
            footer.set_summary("")
            footer.set_hints("n new")
        else:
            subtitle.update(self._subtitle_text(count, currencies, horizons))
            empty.display = False
            table.display = True
            footer.set_summary(f"{count} profile{'s' if count != 1 else ''}")
            footer.set_hints("n new · e edit · c duplicate · ⌫ delete · Enter open")
            if not table.has_focus:
                table.focus()

    @staticmethod
    def _subtitle_text(
        count: int, currencies: set[str], horizons: list[int]
    ) -> str:
        """Compose the quiet context line below the header."""
        parts = [f"{count} profile{'s' if count != 1 else ''}"]
        if currencies:
            parts.append(f"currencies: {', '.join(sorted(currencies))}")
        if horizons:
            hmin, hmax = min(horizons), max(horizons)
            range_str = f"{hmin} months" if hmin == hmax else f"{hmin}–{hmax} months"
            parts.append(f"horizons: {range_str}")
        return " · ".join(parts)

    def refresh_data(self) -> None:
        self.load_profiles()

    def _selected_profile_id(self) -> int | None:
        table = self.query_one("#forecast-profiles-table", DataTable)
        if table.cursor_row is not None and 0 <= table.cursor_row < len(self._profile_ids):
            return self._profile_ids[table.cursor_row]
        return None

    def _selected_profile_name(self) -> str | None:
        table = self.query_one("#forecast-profiles-table", DataTable)
        if table.cursor_row is not None and 0 <= table.cursor_row < len(self._profile_ids):
            try:
                row = table.get_row_at(table.cursor_row)
                return str(row[0]) if row else None
            except Exception:
                return None
        return None

    # ---------------- Actions ----------------

    def action_new_profile(self) -> None:
        def on_saved(result):
            if result is None:
                return
            self.load_profiles()
            if isinstance(result, ProfileFormResult) and result.created:
                self.notify("Profile created")

        self.app.push_screen(ForecastProfileFormModal(self.db_manager), on_saved)

    def action_edit_profile(self) -> None:
        profile_id = self._selected_profile_id()
        if profile_id is None:
            self.notify("No profile selected", severity="warning")
            return

        try:
            modal = ForecastProfileFormModal(self.db_manager, profile_id=profile_id)
        except ValueError:
            self.notify("Profile no longer exists", severity="warning")
            self.load_profiles()
            return

        def on_saved(result):
            if result is None:
                return
            if result == ForecastProfileFormModal.DELETE_SENTINEL:
                self._confirm_delete(profile_id)
                return
            self.load_profiles()
            if isinstance(result, ProfileFormResult) and not result.created:
                if result.lines_truncated or result.overrides_deleted:
                    n_lines = len(result.lines_truncated)
                    n_ovrs = result.overrides_deleted
                    self.notify(
                        f"Horizon shrink truncated {n_lines} line(s) and "
                        f"deleted {n_ovrs} override(s).",
                        severity="warning",
                        timeout=8,
                    )
                else:
                    self.notify("Profile updated")

        self.app.push_screen(modal, on_saved)

    def action_duplicate_profile(self) -> None:
        profile_id = self._selected_profile_id()
        if profile_id is None:
            self.notify("No profile selected", severity="warning")
            return

        try:
            modal = DuplicateProfileModal(self.db_manager, source_id=profile_id)
        except ValueError:
            self.notify("Profile no longer exists", severity="warning")
            self.load_profiles()
            return

        def on_saved(new_id):
            if new_id is None:
                return
            self.load_profiles()
            self.notify("Profile duplicated")

        self.app.push_screen(modal, on_saved)

    def action_delete_profile(self) -> None:
        profile_id = self._selected_profile_id()
        if profile_id is None:
            self.notify("No profile selected", severity="warning")
            return
        self._confirm_delete(profile_id)

    def _confirm_delete(self, profile_id: int) -> None:
        name = self._selected_profile_name() or f"profile {profile_id}"

        def on_confirmed(confirmed: bool) -> None:
            if not confirmed:
                return
            try:
                with self.db_manager.get_session() as session:
                    service = ForecastService(session)
                    service.delete_profile(profile_id)
            except ValueError:
                self.notify("Profile no longer exists", severity="warning")
                self.load_profiles()
                return
            except Exception as e:
                self.notify(f"Error deleting profile: {e}", severity="error")
                return
            self.load_profiles()
            self.notify(f"Profile '{name}' deleted")

        self.app.push_screen(
            ConfirmDialog(f"Delete '{name}' and all its lines and overrides?"),
            on_confirmed,
        )

    def action_open_profile(self) -> None:
        profile_id = self._selected_profile_id()
        if profile_id is None:
            self.notify("No profile selected", severity="warning")
            return

        from ledger.tui.screens.forecast_profile_detail import (
            ForecastProfileDetailScreen,
        )

        self.app.push_screen(
            ForecastProfileDetailScreen(self.db_manager, profile_id)
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """DataTable consumes Enter as row-select; route it to open_profile."""
        if event.data_table.id == "forecast-profiles-table":
            self.action_open_profile()
