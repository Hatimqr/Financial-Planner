"""Period management modal for creating/editing/deleting custom periods."""

from __future__ import annotations

from datetime import date

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, RadioButton, RadioSet, Select, Static

from ledger.db.connection import DatabaseManager
from ledger.services.period_service import (
    BUILTIN_PERIODS,
    RELATIVE_PRESETS,
    PeriodService,
    resolve_builtin,
)


class PeriodManagerModal(ModalScreen[bool]):
    """Modal for viewing and managing custom time periods."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("n", "new_period", "New", show=False),
        Binding("e", "edit_period", "Edit", show=False),
        Binding("backspace", "delete_period", "Delete", show=False),
        Binding("s", "set_default", "Set Default", show=False),
    ]

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager
        self._custom_period_ids: list[int] = []
        self._all_period_keys: list[str] = []  # Keys for both tables combined
        self._changed = False

    def compose(self) -> ComposeResult:
        yield Container(
            Static("Manage Periods", classes="modal-title"),
            Static("", id="default-period-display"),
            Static("Built-in", classes="section-title"),
            DataTable(id="builtin-periods-table"),
            Static("Custom", classes="section-title"),
            DataTable(id="custom-periods-table"),
            Horizontal(
                Button("[n] New", id="btn-new", variant="primary"),
                Button("[e] Edit", id="btn-edit"),
                Button("[s] Set Default", id="btn-set-default"),
                Button("[⌫] Delete", id="btn-delete", variant="error"),
                Button("Close [Esc]", id="btn-close"),
                classes="button-row",
            ),
            classes="modal period-manager-modal",
        )

    def on_mount(self) -> None:
        # Built-in table
        builtin_table = self.query_one("#builtin-periods-table", DataTable)
        builtin_table.cursor_type = "row"
        builtin_table.add_columns("#", "Label", "Date Range")

        # Custom table
        custom_table = self.query_one("#custom-periods-table", DataTable)
        custom_table.cursor_type = "row"
        custom_table.add_columns("#", "Label", "Type", "Date Range")

        self._load_all_periods()

    def _load_all_periods(self) -> None:
        self._all_period_keys = []
        self._custom_period_ids = []

        with self.db_manager.get_session() as session:
            service = PeriodService(session)
            default_key = service.get_default_period_key()

        # Update default display
        default_label = default_key
        for key, label in BUILTIN_PERIODS:
            if key == default_key:
                default_label = label
                break
        self.query_one("#default-period-display", Static).update(
            f"Default startup period: {default_label}"
        )

        # Built-in table
        builtin_table = self.query_one("#builtin-periods-table", DataTable)
        builtin_table.clear()
        for i, (key, label) in enumerate(BUILTIN_PERIODS):
            start, end = resolve_builtin(key)
            range_str = f"{start.strftime('%b %d')} → {end.strftime('%b %d, %Y')}"
            marker = " ★" if key == default_key else ""
            builtin_table.add_row(str(i + 1), f"{label}{marker}", range_str)
            self._all_period_keys.append(key)

        # Custom table
        self._load_custom_periods()

    def _load_custom_periods(self) -> None:
        table = self.query_one("#custom-periods-table", DataTable)
        table.clear()
        self._custom_period_ids = []

        with self.db_manager.get_session() as session:
            service = PeriodService(session)
            customs = service.get_custom_periods()
            default_key = service.get_default_period_key()

            if not customs:
                table.add_row("-", "(none)", "", "Press 'n' to create")
                return

            for i, period in enumerate(customs):
                shortcut = str(len(BUILTIN_PERIODS) + i + 1)
                resolved = service.resolve_period(period)
                range_str = f"{resolved.start_date.strftime('%b %d')} → {resolved.end_date.strftime('%b %d, %Y')}"
                type_label = "Relative" if period.period_type == "relative" else "Fixed"
                key = f"custom-{period.id}"
                marker = " ★" if key == default_key else ""
                table.add_row(shortcut, f"{period.label}{marker}", type_label, range_str)
                self._custom_period_ids.append(period.id)
                self._all_period_keys.append(key)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn = event.button.id
        if btn == "btn-close":
            self.dismiss(self._changed)
        elif btn == "btn-new":
            self.action_new_period()
        elif btn == "btn-edit":
            self.action_edit_period()
        elif btn == "btn-delete":
            self.action_delete_period()
        elif btn == "btn-set-default":
            self.action_set_default()

    def action_new_period(self) -> None:
        def on_saved(result):
            if result:
                self._changed = True
                self._load_custom_periods()

        self.app.push_screen(PeriodFormModal(self.db_manager), on_saved)

    def action_edit_period(self) -> None:
        period_id = self._get_selected_custom_period_id()
        if period_id is None:
            self.notify("Select a custom period to edit", severity="warning")
            return

        def on_saved(result):
            if result:
                self._changed = True
                self._load_custom_periods()

        self.app.push_screen(PeriodFormModal(self.db_manager, period_id=period_id), on_saved)

    def action_delete_period(self) -> None:
        period_id = self._get_selected_custom_period_id()
        if period_id is None:
            self.notify("Select a custom period to delete", severity="warning")
            return

        from ledger.tui.widgets.confirm_dialog import ConfirmDialog

        def on_confirmed(confirmed: bool) -> None:
            if confirmed:
                try:
                    with self.db_manager.get_session() as session:
                        PeriodService(session).delete_period(period_id)
                    self._changed = True
                    self._load_custom_periods()
                    self.notify("Period deleted")
                except Exception as e:
                    self.notify(f"Error: {e}", severity="error")

        self.app.push_screen(
            ConfirmDialog("Delete this custom period?"),
            on_confirmed,
        )

    def _get_selected_custom_period_id(self) -> int | None:
        table = self.query_one("#custom-periods-table", DataTable)
        if table.cursor_row is not None and 0 <= table.cursor_row < len(self._custom_period_ids):
            return self._custom_period_ids[table.cursor_row]
        return None

    def _get_focused_period_key(self) -> str | None:
        """Get the key of whichever period is focused in either table."""
        # Check builtin table
        builtin_table = self.query_one("#builtin-periods-table", DataTable)
        if builtin_table.has_focus and builtin_table.cursor_row is not None:
            idx = builtin_table.cursor_row
            if 0 <= idx < len(BUILTIN_PERIODS):
                return BUILTIN_PERIODS[idx][0]

        # Check custom table
        custom_table = self.query_one("#custom-periods-table", DataTable)
        if custom_table.has_focus and custom_table.cursor_row is not None:
            idx = custom_table.cursor_row
            if 0 <= idx < len(self._custom_period_ids):
                return f"custom-{self._custom_period_ids[idx]}"

        # Fallback: try builtin table cursor even without focus
        if builtin_table.cursor_row is not None:
            idx = builtin_table.cursor_row
            if 0 <= idx < len(BUILTIN_PERIODS):
                return BUILTIN_PERIODS[idx][0]

        return None

    def action_set_default(self) -> None:
        """Set the focused period as the default startup period."""
        key = self._get_focused_period_key()
        if key is None:
            self.notify("Select a period first", severity="warning")
            return

        try:
            with self.db_manager.get_session() as session:
                PeriodService(session).set_default_period_key(key)
            self._changed = True
            self._all_period_keys = []
            self._load_all_periods()
            self.notify(f"Default period set")
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")

    def action_close(self) -> None:
        self.dismiss(self._changed)


class PeriodFormModal(ModalScreen[bool]):
    """Modal for creating or editing a custom period."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "save", "Save", show=False),
    ]

    def action_save(self) -> None:
        self._save()

    def __init__(self, db_manager: DatabaseManager, period_id: int | None = None):
        super().__init__()
        self.db_manager = db_manager
        self.period_id = period_id

    def compose(self) -> ComposeResult:
        title = "Edit Period" if self.period_id else "New Period"

        # Build relative preset options
        preset_options = [(label, key) for key, label in RELATIVE_PRESETS.items()]

        yield Container(
            Static(title, classes="modal-title"),
            Label("Label"),
            Input(id="period-label", placeholder="e.g. Q1 2025, Summer Trip", classes="form-field"),
            Label("Type"),
            RadioSet(
                RadioButton("Fixed dates", id="type-fixed"),
                RadioButton("Relative", id="type-relative"),
                id="period-type-set",
            ),
            Vertical(
                Label("From (YYYY-MM-DD)"),
                Input(id="period-start", placeholder="YYYY-MM-DD", classes="form-field"),
                Label("To (YYYY-MM-DD)"),
                Input(id="period-end", placeholder="YYYY-MM-DD", classes="form-field"),
                id="fixed-fields",
            ),
            Vertical(
                Label("Preset"),
                Select(preset_options, id="period-preset", prompt="Select a preset...", classes="form-field"),
                id="relative-fields",
            ),
            Static("", id="error-display", classes="modal-error"),
            Horizontal(
                Button("Cancel [Esc]", id="btn-cancel"),
                Button("Save [^S]", id="btn-save", variant="primary"),
                classes="button-row",
            ),
            classes="modal period-form-modal",
        )

    def on_mount(self) -> None:
        # Default: show fixed fields, hide relative
        self.query_one("#relative-fields").display = False

        # If editing, pre-populate fields
        if self.period_id:
            self._load_existing()

    def _load_existing(self) -> None:
        with self.db_manager.get_session() as session:
            service = PeriodService(session)
            periods = service.get_custom_periods()
            period = next((p for p in periods if p.id == self.period_id), None)
            if not period:
                return

            self.query_one("#period-label", Input).value = period.label

            if period.period_type == "relative":
                self.query_one("#type-relative", RadioButton).value = True
                self.query_one("#fixed-fields").display = False
                self.query_one("#relative-fields").display = True
                if period.relative_key:
                    self.query_one("#period-preset", Select).value = period.relative_key
            else:
                self.query_one("#type-fixed", RadioButton).value = True
                self.query_one("#fixed-fields").display = True
                self.query_one("#relative-fields").display = False
                if period.start_date:
                    self.query_one("#period-start", Input).value = period.start_date.isoformat()
                if period.end_date:
                    self.query_one("#period-end", Input).value = period.end_date.isoformat()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        is_fixed = event.pressed.id == "type-fixed"
        self.query_one("#fixed-fields").display = is_fixed
        self.query_one("#relative-fields").display = not is_fixed

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(False)
        elif event.button.id == "btn-save":
            self._save()

    def show_error(self, message: str) -> None:
        self.query_one("#error-display", Static).update(message)

    def _clear_field_errors(self) -> None:
        for widget in self.query(".field-error"):
            widget.remove_class("field-error")

    def _save(self) -> None:
        self._clear_field_errors()
        self.show_error("")

        label = self.query_one("#period-label", Input).value.strip()
        if not label:
            self.show_error("Label is required")
            return

        # Determine type
        is_fixed = self.query_one("#type-fixed", RadioButton).value

        try:
            with self.db_manager.get_session() as session:
                service = PeriodService(session)

                if is_fixed:
                    start_str = self.query_one("#period-start", Input).value.strip()
                    end_str = self.query_one("#period-end", Input).value.strip()
                    if not start_str or not end_str:
                        self.show_error("Both dates are required for fixed periods")
                        return
                    try:
                        start_date = date.fromisoformat(start_str)
                        end_date = date.fromisoformat(end_str)
                    except ValueError:
                        self.show_error("Invalid date format. Use YYYY-MM-DD")
                        return

                    if self.period_id:
                        service.update_period(
                            self.period_id,
                            label=label,
                            period_type="fixed",
                            start_date=start_date,
                            end_date=end_date,
                            relative_key=None,
                        )
                    else:
                        service.create_period(
                            label=label,
                            period_type="fixed",
                            start_date=start_date,
                            end_date=end_date,
                        )
                else:
                    preset_val = self.query_one("#period-preset", Select).value
                    if preset_val is None or preset_val == Select.BLANK:
                        self.show_error("Select a relative preset")
                        return

                    if self.period_id:
                        service.update_period(
                            self.period_id,
                            label=label,
                            period_type="relative",
                            relative_key=str(preset_val),
                        )
                    else:
                        service.create_period(
                            label=label,
                            period_type="relative",
                            relative_key=str(preset_val),
                        )

            self.dismiss(True)

        except Exception as e:
            self.show_error(str(e))

    def action_cancel(self) -> None:
        self.dismiss(False)
