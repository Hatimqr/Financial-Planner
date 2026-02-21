"""Budget tracking screen with progress bars."""

from decimal import Decimal

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.screen import Screen
from textual.widgets import ProgressBar, Static

from ledger.db.connection import DatabaseManager
from ledger.services.budget_service import BudgetService


class BudgetProgressWidget(Static):
    """Widget displaying a single budget with progress bar."""

    def __init__(
        self,
        category: str,
        spent: Decimal,
        budgeted: Decimal,
        percentage: Decimal,
        is_over: bool,
    ):
        super().__init__()
        self.category = category
        self.spent = spent
        self.budgeted = budgeted
        self.percentage = percentage
        self.is_over = is_over

    def compose(self) -> ComposeResult:
        # Category name and amounts
        remaining = self.budgeted - self.spent
        status = "OVER" if self.is_over else f"AED {remaining:,.2f} left"

        yield Static(
            f"{self.category:<30} AED {self.spent:>10,.2f} / AED {self.budgeted:>10,.2f}  {status}",
            classes="budget-header",
        )

        # Progress bar (cap at 100 for display, but show actual %)
        display_progress = min(float(self.percentage), 100)
        yield ProgressBar(total=100, show_eta=False, classes="budget-progress")

        # Store percentage for later update
        self._percentage = display_progress

    def on_mount(self) -> None:
        """Update progress bar after mount."""
        progress = self.query_one(ProgressBar)
        progress.advance(self._percentage)

        # Color based on status
        if self.is_over:
            self.add_class("budget-over")
        elif self.percentage > 80:
            self.add_class("budget-warning")
        else:
            self.add_class("budget-ok")


class BudgetsScreen(Screen):
    """Screen for managing and viewing budgets."""

    BINDINGS = [
        Binding("n", "new_budget", "New Budget"),
        Binding("f5", "refresh", "Refresh"),
    ]

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager

    def compose(self) -> ComposeResult:
        yield Container(
            Static("Budgets", classes="screen-title"),
            Static("", id="budget-summary", classes="budget-summary"),
            VerticalScroll(id="budget-list"),
            id="budget-container",
        )

    def on_mount(self) -> None:
        """Load budgets on mount."""
        self.load_budgets()

    def load_budgets(self) -> None:
        """Load and display all budgets."""
        try:
            with self.db_manager.get_session() as session:
                budget_service = BudgetService(session)
                progress_list = budget_service.get_all_budget_progress()

                # Update summary
                total_budgeted = sum(p.budgeted_amount for p in progress_list)
                total_spent = sum(p.spent_amount for p in progress_list)
                summary = self.query_one("#budget-summary", Static)

                if total_budgeted > 0:
                    overall_pct = (total_spent / total_budgeted) * 100
                    summary.update(
                        f"Total: AED {total_spent:,.2f} / AED {total_budgeted:,.2f} ({overall_pct:.1f}%)"
                    )
                else:
                    summary.update("No budgets set. Press 'n' to create one.")

                # Update budget list
                budget_list = self.query_one("#budget-list", VerticalScroll)
                budget_list.remove_children()

                if not progress_list:
                    budget_list.mount(
                        Static(
                            "No budgets configured.\n\nPress 'n' to create your first budget.",
                            classes="no-budgets",
                        )
                    )
                    return

                for progress in sorted(progress_list, key=lambda p: -p.percentage_used):
                    # Get leaf name for display
                    display_name = progress.account_name.split(":")[-1]
                    budget_list.mount(
                        BudgetProgressWidget(
                            category=display_name,
                            spent=progress.spent_amount,
                            budgeted=progress.budgeted_amount,
                            percentage=progress.percentage_used,
                            is_over=progress.is_over_budget,
                        )
                    )

        except Exception as e:
            self.notify(f"Error loading budgets: {e}", severity="error")

    def action_new_budget(self) -> None:
        """Show budget creation form."""
        from ledger.tui.widgets.budget_form import BudgetFormModal

        def on_budget_saved(result):
            if result:
                self.load_budgets()
                self.notify("Budget created successfully!")

        self.app.push_screen(BudgetFormModal(self.db_manager), on_budget_saved)

    def refresh_data(self) -> None:
        """Refresh budget data (common screen interface)."""
        self.load_budgets()

    def action_refresh(self) -> None:
        self.refresh_data()
        self.notify("Budgets refreshed", severity="information")
