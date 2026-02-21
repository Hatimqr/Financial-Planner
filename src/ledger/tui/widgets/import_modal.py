"""CSV import modal for importing bank statements."""

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Select, Static

from ledger.db.connection import DatabaseManager
from ledger.services.account_service import AccountService
from ledger.services.import_service import BANK_PRESETS, ImportService


class ImportModal(ModalScreen):
    """Modal for importing CSV bank statements."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def action_cancel(self) -> None:
        self.dismiss(None)

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager
        self._preview = None

    def compose(self) -> ComposeResult:
        preset_options = [(name.capitalize(), name) for name in BANK_PRESETS]
        yield Container(
            Static("Import CSV", classes="modal-title"),
            Static("", id="import_error", classes="modal-error"),
            Vertical(
                Label("CSV File Path"),
                Input(placeholder="/path/to/statement.csv", id="file_path_input"),
                Label("Bank Format"),
                Select(options=preset_options, id="preset_select", value="generic"),
                Label("Source Account (your bank account)"),
                Select(options=[], id="source_account_select", prompt="Select account"),
                Label("Default Target Account (for uncategorized)"),
                Select(options=[], id="target_account_select", prompt="Select account"),
                Horizontal(
                    Button("Preview", variant="primary", id="preview_btn"),
                    Button("Import", variant="success", id="import_btn", disabled=True),
                    Button("Cancel", variant="default", id="cancel_btn"),
                    classes="button-row",
                ),
                Static("", id="preview_summary"),
                VerticalScroll(
                    DataTable(id="preview_table", zebra_stripes=True),
                    id="preview_scroll",
                ),
            ),
            classes="modal import-modal",
        )

    def on_mount(self) -> None:
        try:
            with self.db_manager.get_session() as session:
                service = AccountService(session)
                accounts = service.get_leaf_accounts()
                options = [(acc.name, str(acc.id)) for acc in accounts]

                self.query_one("#source_account_select", Select).set_options(options)
                self.query_one("#target_account_select", Select).set_options(options)

        except Exception as e:
            self._show_error(f"Error loading accounts: {e}")

        # Set up preview table columns
        table = self.query_one("#preview_table", DataTable)
        table.add_columns("Row", "Date", "Description", "Amount", "Status")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.dismiss(None)
        elif event.button.id == "preview_btn":
            self._do_preview()
        elif event.button.id == "import_btn":
            self._do_import()

    def _do_preview(self) -> None:
        """Preview the CSV file."""
        file_path_str = self.query_one("#file_path_input", Input).value.strip()
        if not file_path_str:
            self._show_error("Please enter a file path")
            return

        file_path = Path(file_path_str).expanduser()
        if not file_path.exists():
            self._show_error(f"File not found: {file_path}")
            return

        source_val = self.query_one("#source_account_select", Select).value
        if source_val == Select.BLANK:
            self._show_error("Please select a source account")
            return

        preset_name = self.query_one("#preset_select", Select).value
        mapping = BANK_PRESETS.get(preset_name, BANK_PRESETS["generic"])

        try:
            with self.db_manager.get_session() as session:
                service = ImportService(session)
                self._preview = service.preview_csv(
                    file_path=file_path,
                    mapping=mapping,
                    source_account_id=int(source_val),
                )

            # Update summary
            summary = self.query_one("#preview_summary", Static)
            summary.update(
                f"Total: {self._preview.total_rows} | "
                f"Valid: {self._preview.valid_rows} | "
                f"Duplicates: {self._preview.duplicate_rows} | "
                f"Errors: {self._preview.error_rows}"
            )

            # Fill preview table
            table = self.query_one("#preview_table", DataTable)
            table.clear()

            for row in self._preview.rows[:50]:  # Show first 50
                if row.error:
                    status = f"ERROR: {row.error}"
                elif row.is_duplicate:
                    status = "DUPLICATE"
                else:
                    status = "OK"

                amount_str = f"AED {row.amount:,.2f}" if row.amount >= 0 else f"-AED {abs(row.amount):,.2f}"

                table.add_row(
                    str(row.row_number),
                    row.transaction_date.strftime("%Y-%m-%d"),
                    row.description[:30] if row.description else "",
                    amount_str,
                    status,
                )

            # Enable import button if there are valid rows
            import_btn = self.query_one("#import_btn", Button)
            import_btn.disabled = self._preview.valid_rows == 0
            self._show_error("")

        except Exception as e:
            self._show_error(f"Preview error: {e}")

    def _do_import(self) -> None:
        """Import the previewed CSV."""
        file_path_str = self.query_one("#file_path_input", Input).value.strip()
        source_val = self.query_one("#source_account_select", Select).value
        target_val = self.query_one("#target_account_select", Select).value

        if target_val == Select.BLANK:
            self._show_error("Please select a target account")
            return

        preset_name = self.query_one("#preset_select", Select).value
        mapping = BANK_PRESETS.get(preset_name, BANK_PRESETS["generic"])

        try:
            with self.db_manager.get_session() as session:
                service = ImportService(session)
                count = service.import_csv(
                    file_path=Path(file_path_str).expanduser(),
                    mapping=mapping,
                    source_account_id=int(source_val),
                    target_account_id=int(target_val),
                    skip_duplicates=True,
                )
            self.dismiss(count)

        except Exception as e:
            self._show_error(f"Import error: {e}")

    def _show_error(self, message: str) -> None:
        self.query_one("#import_error", Static).update(message)
