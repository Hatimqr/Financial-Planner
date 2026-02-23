"""Modal for editing a single import row."""

from datetime import date
from decimal import Decimal, InvalidOperation

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from ledger.db.connection import DatabaseManager
from ledger.services.account_service import AccountService
from ledger.services.pdf_import_models import (
    PdfPosting,
    ResolvedTransaction,
)


class ImportRowEditModal(ModalScreen):
    """Modal for editing a single transaction from the import review."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "save", "Save", show=False),
    ]

    def action_save(self) -> None:
        self._save()

    def __init__(self, db_manager: DatabaseManager, resolved_txn: ResolvedTransaction):
        super().__init__()
        self.db_manager = db_manager
        self.resolved_txn = resolved_txn
        self._account_options: list[tuple[str, str]] = []

    def compose(self) -> ComposeResult:
        txn = self.resolved_txn.transaction
        # Debit = money in (positive), Credit = money out (negative)
        debit_val = str(txn.amount) if txn.amount > 0 else ""
        credit_val = str(abs(txn.amount)) if txn.amount < 0 else ""

        yield Container(
            Static("Edit Import Transaction", classes="modal-title"),
            Static("", id="error-display", classes="modal-error"),
            Vertical(
                Label("Description"),
                Input(value=txn.description, id="edit_description", classes="form-field"),
                Label("Date (YYYY-MM-DD)"),
                Input(value=txn.date.isoformat(), id="edit_date", placeholder="YYYY-MM-DD", classes="form-field"),
                Horizontal(
                    Vertical(
                        Label("Debit (money in)"),
                        Input(value=debit_val, placeholder="0.00", id="edit_debit", classes="form-field"),
                    ),
                    Vertical(
                        Label("Credit (money out)"),
                        Input(value=credit_val, placeholder="0.00", id="edit_credit", classes="form-field"),
                    ),
                    classes="edit-amount-row",
                ),
                Label("Target Account"),
                Select(options=[], id="edit_account_select", prompt="Select account", classes="form-field"),
                Label("Notes (read-only)"),
                Static(self._build_notes(), id="edit_notes", classes="import-edit-notes"),
                Horizontal(
                    Button("Cancel [Esc]", variant="default", id="edit_cancel_btn"),
                    Button("Save [^S]", variant="primary", id="edit_save_btn"),
                    classes="button-row",
                ),
            ),
            classes="modal",
        )

    def on_mount(self) -> None:
        try:
            with self.db_manager.get_session() as session:
                service = AccountService(session)
                accounts = service.get_leaf_accounts()
                self._account_options = [(acc.name, acc.name) for acc in accounts]

            select = self.query_one("#edit_account_select", Select)
            select.set_options(self._account_options)

            # Pre-select current account if it exists in options
            if self.resolved_txn.resolved_postings:
                current = self.resolved_txn.resolved_postings[0].account_name
                for name, val in self._account_options:
                    if val == current:
                        select.value = current
                        break

        except Exception as e:
            self.show_error(f"Error: {e}")

    def _build_notes(self) -> str:
        txn = self.resolved_txn.transaction
        parts = []
        if txn.original_description:
            parts.append(f"Original: {txn.original_description}")
        if txn.foreign_currency_note:
            parts.append(f"Foreign: {txn.foreign_currency_note}")
        if txn.reference:
            parts.append(f"Ref: {txn.reference}")
        return "\n".join(parts) if parts else "(none)"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "edit_cancel_btn":
            self.dismiss(None)
        elif event.button.id == "edit_save_btn":
            self._save()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def show_error(self, message: str) -> None:
        self.query_one("#error-display", Static).update(message)

    def _clear_field_errors(self) -> None:
        for widget in self.query(".field-error"):
            widget.remove_class("field-error")

    def _save(self) -> None:
        """Save edits back to the ResolvedTransaction."""
        self._clear_field_errors()
        description = self.query_one("#edit_description", Input).value.strip()
        date_str = self.query_one("#edit_date", Input).value.strip()
        debit_str = self.query_one("#edit_debit", Input).value.strip()
        credit_str = self.query_one("#edit_credit", Input).value.strip()
        account_val = self.query_one("#edit_account_select", Select).value

        if not description:
            self.show_error("Description is required")
            return

        try:
            txn_date = date.fromisoformat(date_str)
        except ValueError:
            self.show_error("Invalid date format")
            return

        # Exactly one of debit/credit must be filled
        if debit_str and credit_str:
            self.show_error("Fill either Debit or Credit, not both")
            return
        if not debit_str and not credit_str:
            self.show_error("Enter a Debit or Credit amount")
            return

        try:
            if debit_str:
                amount = Decimal(debit_str)  # positive = money in
            else:
                amount = -Decimal(credit_str)  # negative = money out
        except (InvalidOperation, ValueError):
            self.show_error("Invalid amount")
            return

        # Update the transaction
        txn = self.resolved_txn.transaction
        txn.description = description
        txn.date = txn_date
        txn.amount = amount

        # Update account if changed
        if account_val != Select.BLANK:
            account_name = str(account_val)
            txn.postings = [PdfPosting(account=account_name, amount=abs(amount))]

            # Re-resolve the account
            with self.db_manager.get_session() as session:
                from ledger.services.pdf_import_service import PdfImportService
                svc = PdfImportService(session)
                resolution = svc._resolve_single_account(account_name)
            self.resolved_txn.resolved_postings = [resolution]

        self.dismiss(self.resolved_txn)
