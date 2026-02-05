"""Budget form modal for creating budgets."""

from datetime import date
from decimal import Decimal, InvalidOperation

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from ledger.db.connection import DatabaseManager
from ledger.services.account_service import AccountService
from ledger.services.budget_service import BudgetService


class BudgetFormModal(ModalScreen):
    """Modal dialog for creating a budget."""

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager
        self.account_options = []

    def compose(self) -> ComposeResult:
        yield Container(
            Static("New Budget", classes="modal-title"),
            Static("", id="error_display", classes="modal-error"),
            Vertical(
                Label("Expense Account"),
                Select(
                    options=[],
                    id="account_select",
                    prompt="Select expense account",
                    classes="form-field",
                ),
                Label("Budget Amount"),
                Input(placeholder="0.00", id="amount_input", classes="form-field"),
                Label("Period"),
                Select(
                    options=[
                        ("Monthly", "monthly"),
                        ("Quarterly", "quarterly"),
                        ("Yearly", "yearly"),
                    ],
                    id="period_select",
                    value="monthly",
                    classes="form-field",
                ),
                Horizontal(
                    Button("Cancel", variant="default", id="cancel_btn"),
                    Button("Save", variant="primary", id="save_btn"),
                    classes="button-row",
                ),
            ),
            classes="modal",
        )

    def on_mount(self) -> None:
        """Load expense accounts when mounted."""
        try:
            with self.db_manager.get_session() as session:
                service = AccountService(session)
                # Get only expense leaf accounts
                accounts = service.get_leaf_accounts(account_type="expense")
                self.account_options = [(acc.name, str(acc.id)) for acc in accounts]

                account_select = self.query_one("#account_select", Select)
                account_select.set_options(self.account_options)

        except Exception as e:
            self.show_error(f"Error loading accounts: {e}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel_btn":
            self.dismiss(None)
        elif event.button.id == "save_btn":
            self.save_budget()

    def save_budget(self) -> None:
        """Save the budget."""
        account_id_str = self.query_one("#account_select", Select).value
        amount_str = self.query_one("#amount_input", Input).value.strip()
        period = self.query_one("#period_select", Select).value

        # Validation
        if account_id_str == Select.BLANK:
            self.show_error("Please select an expense account")
            return

        if not amount_str:
            self.show_error("Amount is required")
            return

        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                self.show_error("Amount must be positive")
                return
        except (InvalidOperation, ValueError):
            self.show_error("Invalid amount format")
            return

        try:
            account_id = int(account_id_str)
        except ValueError:
            self.show_error("Invalid account selection")
            return

        try:
            with self.db_manager.get_session() as session:
                budget_service = BudgetService(session)
                budget_service.create_budget(
                    account_id=account_id,
                    amount=amount,
                    period=period,
                    effective_from=date.today().replace(day=1),
                )
                self.dismiss(True)

        except ValueError as e:
            self.show_error(str(e))
        except Exception as e:
            self.show_error(f"Error creating budget: {e}")

    def show_error(self, message: str) -> None:
        """Display error message."""
        error_display = self.query_one("#error_display", Static)
        error_display.update(message)
