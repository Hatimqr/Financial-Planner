"""Account form modal for creating/editing accounts."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from ledger.db.connection import DatabaseManager
from ledger.services.account_service import AccountService


class AccountFormModal(ModalScreen):
    """Modal dialog for creating a new account."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "save", "Save", show=False),
    ]

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_save(self) -> None:
        self.save_account()

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize account form modal.

        Args:
            db_manager: Database manager instance
        """
        super().__init__()
        self.db_manager = db_manager
        self.error_message = ""

    def compose(self) -> ComposeResult:
        """Create form widgets."""
        yield Container(
            Static("Create Account", classes="modal-title"),
            Static(self.error_message, id="error-display", classes="modal-error"),
            Vertical(
                Label("Account Name (e.g., Assets:Bank:Chase)"),
                Input(
                    placeholder="Assets:Bank:Chase",
                    id="name_input",
                    classes="form-field",
                ),
                Label("Account Type"),
                Select(
                    options=[
                        ("Asset", "asset"),
                        ("Liability", "liability"),
                        ("Equity", "equity"),
                        ("Income", "income"),
                        ("Expense", "expense"),
                    ],
                    id="type_select",
                    classes="form-field",
                    value="asset",
                ),
                Label("Currency (default: USD)"),
                Input(
                    placeholder="USD",
                    id="currency_input",
                    classes="form-field",
                    value="USD",
                ),
                Label("Notes (optional)"),
                Input(placeholder="Optional notes", id="notes_input", classes="form-field"),
                Horizontal(
                    Button("Cancel [Esc]", variant="default", id="cancel_btn"),
                    Button("Save [^S]", variant="primary", id="save_btn"),
                    classes="button-row",
                ),
            ),
            classes="modal",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "cancel_btn":
            self.dismiss(None)
        elif event.button.id == "save_btn":
            self.save_account()

    def _clear_field_errors(self) -> None:
        for widget in self.query(".field-error"):
            widget.remove_class("field-error")

    def save_account(self) -> None:
        """Save the account to the database."""
        self._clear_field_errors()
        name = self.query_one("#name_input", Input).value.strip()
        account_type = self.query_one("#type_select", Select).value
        currency = self.query_one("#currency_input", Input).value.strip() or "USD"
        notes = self.query_one("#notes_input", Input).value.strip()

        # Validation
        if not name:
            self.query_one("#name_input").add_class("field-error")
            self.show_error("Account name is required")
            return

        try:
            with self.db_manager.get_session() as session:
                service = AccountService(session)
                account = service.create_account(
                    name=name,
                    account_type=account_type,
                    currency=currency,
                    notes=notes if notes else None,
                )
                # Extract account name before session closes to avoid DetachedInstanceError
                account_name = account.name
                self.dismiss(account_name)
        except ValueError as e:
            self.show_error(str(e))
        except Exception as e:
            self.show_error(f"Error creating account: {e}")

    def show_error(self, message: str) -> None:
        """Display an error message."""
        self.query_one("#error-display", Static).update(message)
