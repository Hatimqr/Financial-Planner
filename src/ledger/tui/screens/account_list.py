"""Account list screen showing all accounts with balances."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import DataTable, Static

from ledger.db.connection import DatabaseManager
from ledger.services.account_service import AccountService


class AccountListScreen(Screen):
    """Screen showing list of all accounts with balances."""

    BINDINGS = [
        Binding("n", "new_account", "New Account"),
    ]

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize account list screen.

        Args:
            db_manager: Database manager instance
        """
        super().__init__()
        self.db_manager = db_manager

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Container(
            Static("💰 Accounts", classes="screen-title"),
            DataTable(id="accounts_table", zebra_stripes=True),
        )

    def on_mount(self) -> None:
        """Set up the screen when it's mounted."""
        table = self.query_one("#accounts_table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Name", "Type", "Currency", "Balance")
        self.load_accounts()

    def load_accounts(self) -> None:
        """Load accounts from database and display in table."""
        table = self.query_one("#accounts_table", DataTable)
        table.clear()

        try:
            with self.db_manager.get_session() as session:
                service = AccountService(session)
                accounts = service.get_account_tree()

                for account in accounts:
                    balance = service.get_account_balance(account.id)

                    # Format balance with color based on account type
                    balance_str = f"AED {balance:,.2f}" if balance >= 0 else f"-AED {abs(balance):,.2f}"

                    # Add indentation for hierarchy
                    depth = account.name.count(":")
                    indent = "  " * depth
                    name_display = f"{indent}{account.name.split(':')[-1]}"

                    if account.is_placeholder:
                        name_display += " 📁"

                    table.add_row(
                        name_display,
                        account.type.capitalize(),
                        account.currency,
                        balance_str,
                    )

            self.notify(f"Loaded {len(accounts)} accounts", severity="information")

        except Exception as e:
            self.notify(f"Error loading accounts: {e}", severity="error")

    def refresh_data(self) -> None:
        """Refresh account data (common screen interface)."""
        self.load_accounts()

    def action_new_account(self) -> None:
        """Show account creation form."""
        from ledger.tui.widgets.account_form import AccountFormModal

        def on_account_saved(account_name):
            if account_name:
                self.load_accounts()
                self.notify(f"Account '{account_name}' created successfully!")

        self.app.push_screen(AccountFormModal(self.db_manager), on_account_saved)
