"""Command palette provider for Ledger TUI."""

from textual.command import DiscoveryHit, Hit, Hits, Provider


class LedgerCommands(Provider):
    """Command provider for Ledger TUI navigation and actions."""

    # Navigation commands: (display_name, action_method_name, help_text)
    COMMANDS = [
        ("Go to Dashboard", "show_dashboard", "View financial overview and KPIs"),
        ("Go to Accounts", "show_accounts", "View and manage accounts"),
        ("Go to Transactions", "show_transactions", "View and manage transactions"),
        ("Go to Reports", "show_reports", "View financial reports"),
        ("Go to Budgets", "show_budgets", "View and manage budgets"),
        ("Go to Forecasts", "show_forecasts", "View and manage forecast profiles"),
        ("New Transaction", "new_transaction", "Create a new transaction"),
        ("New Account", "new_account", "Create a new account"),
        ("New Budget", "new_budget", "Create a new budget"),
        ("Import Statement", "show_import", "Import bank statement from JSON/PDF"),
        ("Search Transactions", "search", "Search for transactions"),
        ("Refresh View", "refresh", "Refresh current view"),
        ("Quit Application", "quit", "Exit the application"),
    ]

    async def discover(self) -> Hits:
        """Show all commands when palette first opens."""
        for display, action, help_text in self.COMMANDS:
            yield DiscoveryHit(
                display,
                self._make_callback(action),
                help=help_text,
            )

    async def search(self, query: str) -> Hits:
        """Search for matching commands."""
        matcher = self.matcher(query)

        for display, action, help_text in self.COMMANDS:
            match = matcher.match(display)
            if match > 0:
                yield Hit(
                    match,
                    matcher.highlight(display),
                    command=self._make_callback(action),
                    help=help_text,
                )

    def _make_callback(self, action: str):
        """Create a callback for the given action."""
        async def callback() -> None:
            await self._run_command(action)
        return callback

    async def _run_command(self, command: str) -> None:
        """Execute a command."""
        app = self.app
        if command == "show_dashboard":
            app.action_show_dashboard()
        elif command == "show_accounts":
            app.action_show_accounts()
        elif command == "show_transactions":
            app.action_show_transactions()
        elif command == "show_reports":
            app.action_show_reports()
        elif command == "show_budgets":
            app.action_show_budgets()
        elif command == "show_forecasts":
            app.action_show_forecasts()
        elif command == "new_transaction":
            app.action_new_transaction()
        elif command == "new_account":
            app.action_new_account()
        elif command == "new_budget":
            app.action_new_budget()
        elif command == "show_import":
            app.action_show_import()
        elif command == "search":
            app.action_search()
        elif command == "refresh":
            app.action_refresh()
        elif command == "quit":
            app.exit()
