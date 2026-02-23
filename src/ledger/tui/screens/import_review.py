"""Import review screen for reviewing and confirming statement imports."""

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, Label, Select, Static

from ledger.db.connection import DatabaseManager
from ledger.services.account_service import AccountService
from ledger.services.pdf_import_models import ResolvedTransaction
from ledger.services.pdf_import_service import PdfImportService
from ledger.tui.widgets.app_header import AppHeader


class ImportReviewScreen(Screen):
    """Screen for reviewing parsed statement transactions before import."""

    BINDINGS = [
        Binding("escape", "go_back", "Back", show=True),
        Binding("space", "toggle_include", "Toggle", show=True),
        Binding("e", "edit_row", "Edit Row", show=True),
        Binding("c", "confirm_import", "Confirm", show=True),
        Binding("n", "new_account", "New Acct", show=True),
    ]

    def __init__(self, db_manager: DatabaseManager, file_path: str | None = None):
        super().__init__()
        self.db_manager = db_manager
        self.initial_file_path = file_path
        self._resolved: list[ResolvedTransaction] = []
        self._statement = None
        self._source_account_id: int | None = None

    def compose(self) -> ComposeResult:
        yield AppHeader("Import")
        yield Container(
            Horizontal(
                Vertical(
                    Label("File Path"),
                    Input(
                        placeholder="/path/to/statement.json",
                        id="file_path_input",
                        value=self.initial_file_path or "",
                    ),
                    id="import-file-field",
                ),
                Vertical(
                    Label("Source Account (your bank)"),
                    Select(options=[], id="source_account_select", prompt="Select account"),
                    id="import-source-field",
                ),
                Button("Load", variant="primary", id="load_btn"),
                id="import-header",
                classes="import-header-row",
            ),
            Static("", id="import_info"),
            Static("", id="import_error", classes="modal-error"),
            DataTable(id="import_review_table", zebra_stripes=True),
            Static("", id="import_summary"),
            Horizontal(
                Button("Confirm Import", variant="success", id="confirm_btn", disabled=True),
                Button("Cancel", variant="default", id="cancel_btn"),
                classes="button-row",
            ),
            id="import-container",
        )

    NEW_ACCOUNT_SENTINEL = "__new_account__"

    def on_mount(self) -> None:
        # Load account options
        self._reload_account_options()


        # Set up table columns
        table = self.query_one("#import_review_table", DataTable)
        table.cursor_type = "row"
        table.add_columns("✓", "Date", "Description", "Account", "Debit", "Credit", "Status")

        self.query_one("#import_review_table", DataTable).focus()

        # Auto-load if file path was provided
        if self.initial_file_path:
            # Defer to allow mount to complete
            self.set_timer(0.1, self._auto_load)

    def _auto_load(self) -> None:
        self._do_load()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "source_account_select":
            # Clear error highlight when user makes a selection
            event.select.remove_class("field-error")
            self._show_error("")
            # Intercept the "new account" option
            if event.value == self.NEW_ACCOUNT_SENTINEL:
                event.select.value = Select.BLANK
                self.action_new_account()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.action_go_back()
        elif event.button.id == "load_btn":
            self._do_load()
        elif event.button.id == "confirm_btn":
            self.action_confirm_import()

    def _do_load(self) -> None:
        """Load and parse the statement file."""
        file_path_str = self.query_one("#file_path_input", Input).value.strip()
        if not file_path_str:
            self.notify("Please enter a file path", severity="error")
            return

        file_path = Path(file_path_str).expanduser()
        if not file_path.exists():
            self.notify(f"File not found: {file_path}", severity="error")
            return

        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            self.notify("PDF parsing not yet supported. Use JSON.", severity="error")
            return
        elif suffix != ".json":
            self.notify("Unsupported file format. Use .json", severity="error")
            return

        source_select = self.query_one("#source_account_select", Select)
        source_val = source_select.value
        if source_val == Select.BLANK:
            source_select.add_class("field-error")
            self.notify("Please select a source account", severity="error")
            return
        source_select.remove_class("field-error")

        self._source_account_id = int(source_val)

        try:
            with self.db_manager.get_session() as session:
                service = PdfImportService(session)
                self._statement = service.load_json_file(file_path)
                self._resolved = service.resolve_accounts(self._statement)
                service.check_duplicates(self._resolved, self._source_account_id)

            # Show statement info
            info = self.query_one("#import_info", Static)
            period = ""
            if self._statement.statement_period_from and self._statement.statement_period_to:
                period = f" | Period: {self._statement.statement_period_from} to {self._statement.statement_period_to}"
            info.update(
                f"Bank: {self._statement.bank_name} | "
                f"Currency: {self._statement.currency}{period} | "
                f"Opening: {self._statement.opening_balance:,.2f} | "
                f"Closing: {self._statement.closing_balance:,.2f}"
            )

            self._refresh_table()
            self.query_one("#import_review_table", DataTable).focus()
            self.notify(f"Loaded {len(self._resolved)} transactions", severity="information")

        except Exception as e:
            self.notify(f"Error loading file: {e}", severity="error")

    def _refresh_table(self) -> None:
        """Refresh the review table with current resolved transactions."""
        table = self.query_one("#import_review_table", DataTable)
        table.clear()

        new_accounts = 0
        duplicates = 0
        included = 0
        total_amount = 0

        for rt in self._resolved:
            txn = rt.transaction
            check = "✓" if rt.included else " "

            # Determine status
            status_parts = []
            if rt.is_duplicate:
                status_parts.append("DUP")
                duplicates += 1
            for rp in rt.resolved_postings:
                if rp.status in ("new_with_parent", "new_tree"):
                    status_parts.append("NEW")
                    new_accounts += 1
                    break
            status = " ".join(status_parts) if status_parts else "OK"

            # Account display
            account_display = rt.resolved_postings[0].account_name if rt.resolved_postings else "-"
            # Shorten for display
            if len(account_display) > 30:
                account_display = "..." + account_display[-27:]

            # Debit = money in (positive), Credit = money out (negative)
            if txn.amount > 0:
                debit_str = f"{txn.amount:,.2f}"
                credit_str = ""
            else:
                debit_str = ""
                credit_str = f"{abs(txn.amount):,.2f}"

            table.add_row(
                check,
                txn.date.strftime("%Y-%m-%d"),
                txn.description[:35] if len(txn.description) > 35 else txn.description,
                account_display,
                debit_str,
                credit_str,
                status,
            )

            if rt.included:
                included += 1
                total_amount += float(txn.amount)

        # Update summary
        summary = self.query_one("#import_summary", Static)
        summary.update(
            f"Total: {len(self._resolved)} | "
            f"Included: {included} | "
            f"Duplicates: {duplicates} | "
            f"New accounts: {new_accounts} | "
            f"Net amount: {total_amount:,.2f}"
        )

        # Enable confirm button if there are included transactions
        self.query_one("#confirm_btn", Button).disabled = included == 0

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle Enter on a table row — open edit modal."""
        self.action_edit_row()

    def action_toggle_include(self) -> None:
        """Toggle include/exclude for the selected row."""
        table = self.query_one("#import_review_table", DataTable)
        if table.cursor_row is not None and 0 <= table.cursor_row < len(self._resolved):
            cursor_pos = table.cursor_row
            rt = self._resolved[cursor_pos]
            rt.included = not rt.included
            # Update just the first column instead of rebuilding the whole table
            row_key = table._row_order[cursor_pos]  # noqa: SLF001
            table.update_cell(row_key, table._column_order[0], "✓" if rt.included else " ")  # noqa: SLF001
            self._update_summary()

    def _update_summary(self) -> None:
        """Update the summary line and confirm button without rebuilding the table."""
        included = sum(1 for rt in self._resolved if rt.included)
        duplicates = sum(1 for rt in self._resolved if rt.is_duplicate)
        new_accounts = 0
        total_amount = 0.0
        for rt in self._resolved:
            for rp in rt.resolved_postings:
                if rp.status in ("new_with_parent", "new_tree"):
                    new_accounts += 1
                    break
            if rt.included:
                total_amount += float(rt.transaction.amount)

        summary = self.query_one("#import_summary", Static)
        summary.update(
            f"Total: {len(self._resolved)} | "
            f"Included: {included} | "
            f"Duplicates: {duplicates} | "
            f"New accounts: {new_accounts} | "
            f"Net amount: {total_amount:,.2f}"
        )
        self.query_one("#confirm_btn", Button).disabled = included == 0

    def action_edit_row(self) -> None:
        """Edit the selected transaction."""
        table = self.query_one("#import_review_table", DataTable)
        if table.cursor_row is None or table.cursor_row >= len(self._resolved):
            self.notify("No transaction selected", severity="warning")
            return

        from ledger.tui.widgets.import_row_edit import ImportRowEditModal

        rt = self._resolved[table.cursor_row]
        row_idx = table.cursor_row

        def on_edited(result):
            if result is not None:
                self._resolved[row_idx] = result
                self._refresh_table()

        self.app.push_screen(
            ImportRowEditModal(self.db_manager, rt),
            on_edited,
        )

    def action_confirm_import(self) -> None:
        """Commit the import to the database."""
        if not self._resolved or self._source_account_id is None:
            self.notify("Nothing to import", severity="warning")
            return

        included = [rt for rt in self._resolved if rt.included]
        if not included:
            self.notify("No transactions selected for import", severity="warning")
            return

        # Collect new accounts for confirmation
        new_accounts = set()
        for rt in included:
            for rp in rt.resolved_postings:
                if rp.status in ("new_with_parent", "new_tree"):
                    new_accounts.add(f"{rp.account_name} ({rp.account_type})")

        if new_accounts:
            from ledger.tui.widgets.confirm_dialog import ConfirmDialog

            msg = f"This will create {len(new_accounts)} new account(s):\n"
            for acc in sorted(new_accounts):
                msg += f"  - {acc}\n"
            msg += f"\nand import {len(included)} transaction(s). Proceed?"

            def on_confirmed(confirmed):
                if confirmed:
                    self._do_commit()

            self.app.push_screen(
                ConfirmDialog(msg, confirm_label="Import", confirm_variant="success"),
                on_confirmed,
            )
        else:
            self._do_commit()

    def _do_commit(self) -> None:
        """Actually commit the import."""
        try:
            with self.db_manager.get_session() as session:
                service = PdfImportService(session)
                count = service.commit_import(self._resolved, self._source_account_id)
            self.notify(f"Successfully imported {count} transactions!")
            self.action_go_back()
        except Exception as e:
            self._show_error(f"Import error: {e}")

    def action_new_account(self) -> None:
        """Open the new account modal and reload options on success."""
        from ledger.tui.widgets.account_form import AccountFormModal

        def on_saved(result):
            if result:
                self.notify(f"Account '{result}' created!")
                # Find the new account's ID and auto-select it
                try:
                    with self.db_manager.get_session() as session:
                        service = AccountService(session)
                        account = service.get_account_by_name(result)
                        new_id = str(account.id) if account else None
                except Exception:
                    new_id = None
                self._reload_account_options(auto_select_id=new_id)

        self.app.push_screen(AccountFormModal(self.db_manager), on_saved)

    def _reload_account_options(self, auto_select_id: str | None = None) -> None:
        """Reload the source account select options.

        Args:
            auto_select_id: If provided, auto-select this account ID after reload.
        """
        try:
            with self.db_manager.get_session() as session:
                service = AccountService(session)
                accounts = service.get_leaf_accounts()
                options: list[tuple[str, str]] = [(acc.name, str(acc.id)) for acc in accounts]
            options.append(("+ Create New Account...", self.NEW_ACCOUNT_SENTINEL))
            select = self.query_one("#source_account_select", Select)
            select.set_options(options)
            if auto_select_id:
                select.value = auto_select_id
        except Exception as e:
            self._show_error(f"Error loading accounts: {e}")

    def action_go_back(self) -> None:
        """Go back to previous screen."""
        self.app.pop_screen()

    def refresh_data(self) -> None:
        """Common screen interface."""
        if self._resolved:
            self._refresh_table()

    def _show_error(self, message: str) -> None:
        self.query_one("#import_error", Static).update(message)
