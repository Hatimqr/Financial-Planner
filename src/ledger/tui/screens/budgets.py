"""Budget tracking screen with progress bars."""

from decimal import Decimal

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Input, ProgressBar, Static

from ledger.db.connection import DatabaseManager
from ledger.services.budget_service import BudgetProgress, BudgetService
from ledger.tui.widgets.app_header import AppHeader
from ledger.tui.widgets.status_footer import StatusFooter


def _breadcrumb(account_name: str) -> tuple[str, str]:
    """Return (leaf_name, breadcrumb_trail) from a colon-separated path.

    'Expenses:Food:Groceries' -> ('Groceries', 'Food \u2039 Expenses')
    'Expenses:Food'           -> ('Food', 'Expenses')
    'Food'                    -> ('Food', '')
    """
    parts = account_name.split(":")
    leaf = parts[-1]
    if len(parts) > 1:
        trail = " \u2039 ".join(parts[-2::-1])  # reversed parents
    else:
        trail = ""
    return leaf, trail


class BudgetProgressWidget(Static):
    """Widget displaying a single budget with progress bar."""

    can_focus = True

    def __init__(
        self,
        account_name: str,
        spent: Decimal,
        budgeted: Decimal,
        percentage: Decimal,
        is_over: bool,
        period: str = "monthly",
        is_prorated: bool = False,
        prorate_label: str = "",
    ):
        super().__init__()
        self.account_name = account_name
        self.spent = spent
        self.budgeted = budgeted
        self.percentage = percentage
        self.is_over = is_over
        self.period = period
        self.is_prorated = is_prorated
        self.prorate_label = prorate_label

    def compose(self) -> ComposeResult:
        leaf, trail = _breadcrumb(self.account_name)

        # -- Row 1: name + breadcrumb left, period tag right --
        period_tag = "" if self.is_prorated else f" ({self.period.capitalize()})"
        if trail:
            name_line = f"{leaf}{period_tag}  [dim]{trail}[/dim]"
        else:
            name_line = f"{leaf}{period_tag}"

        # -- Row 2 right-hand side: amounts + status --
        if self.is_over:
            over_by = self.spent - self.budgeted
            amount_line = (
                f"[bold red]AED {self.spent:,.2f}[/bold red]"
                f"[dim] / [/dim]AED {self.budgeted:,.2f}"
                f"  [bold red]{self.percentage:.0f}% \u2014 AED {over_by:,.2f} over[/bold red]"
            )
        else:
            remaining = self.budgeted - self.spent
            amount_line = (
                f"AED {self.spent:,.2f}"
                f"[dim] / [/dim]AED {self.budgeted:,.2f}"
                f"  [dim]{self.percentage:.0f}% \u2014 AED {remaining:,.2f} left[/dim]"
            )

        yield Static(name_line, classes="budget-name", markup=True)
        yield Static(amount_line, classes="budget-amounts", markup=True)

        display_progress = min(float(self.percentage), 100)
        yield ProgressBar(total=100, show_eta=False, classes="budget-progress")
        self._percentage = display_progress

        if self.is_prorated and self.prorate_label:
            yield Static(
                f"[dim italic]  \u21b3 {self.prorate_label}[/dim italic]",
                classes="budget-prorate-label",
                markup=True,
            )

    def on_mount(self) -> None:
        """Update progress bar after mount."""
        progress = self.query_one(ProgressBar)
        progress.advance(self._percentage)

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
        Binding("e", "edit_budget", "Edit"),
        Binding("backspace", "delete_budget", "Delete"),
        Binding("j", "cursor_down", "Next", show=False),
        Binding("k", "cursor_up", "Previous", show=False),
        Binding("down", "cursor_down", "Next", show=False),
        Binding("up", "cursor_up", "Previous", show=False),
        Binding("ctrl+slash", "focus_search", "Search"),
        Binding("f5", "refresh", "Refresh"),
    ]

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager
        self._budget_progress: list[BudgetProgress] = []
        self._selected_idx: int | None = None
        self._search_query: str | None = None
        self._search_timer = None

    def compose(self) -> ComposeResult:
        yield AppHeader("Budgets")
        yield Container(
            Input(placeholder="Search budgets... (Ctrl+/ to focus)", id="budget-search"),
            Static("", id="budget-summary", classes="budget-summary"),
            VerticalScroll(id="budget-list"),
            id="budget-container",
        )
        yield StatusFooter(id="budgets-footer")

    def on_mount(self) -> None:
        """Load budgets on mount."""
        self.load_budgets()

    def load_budgets(self) -> None:
        """Load and display all budgets using the global period bar window."""
        try:
            start = self.app.period_start
            end = self.app.period_end

            with self.db_manager.get_session() as session:
                budget_service = BudgetService(session)
                all_progress = sorted(
                    budget_service.get_all_budget_progress(start, end),
                    key=lambda p: -p.percentage_used,
                )

                # Filter by search query
                if self._search_query:
                    q = self._search_query.lower()
                    self._budget_progress = [
                        p for p in all_progress
                        if q in p.account_name.lower()
                    ]
                else:
                    self._budget_progress = all_progress

                # Update summary
                total_budgeted = sum(p.budgeted_amount for p in self._budget_progress)
                total_spent = sum(p.spent_amount for p in self._budget_progress)
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

                if not self._budget_progress:
                    self._selected_idx = None
                    budget_list.mount(
                        Static(
                            "No budgets configured.\n\nPress 'n' to create your first budget.",
                            classes="no-budgets",
                        )
                    )
                    return

                for progress in self._budget_progress:
                    budget_list.mount(
                        BudgetProgressWidget(
                            account_name=progress.account_name,
                            spent=progress.spent_amount,
                            budgeted=progress.budgeted_amount,
                            percentage=progress.percentage_used,
                            is_over=progress.is_over_budget,
                            period=progress.period,
                            is_prorated=progress.is_prorated,
                            prorate_label=progress.prorate_label,
                        )
                    )

                # Restore or initialize selection
                if self._budget_progress:
                    if self._selected_idx is None or self._selected_idx >= len(self._budget_progress):
                        self._selected_idx = 0
                    self._update_selection()

        except Exception as e:
            self.notify(f"Error loading budgets: {e}", severity="error")

    def _get_budget_widgets(self) -> list[BudgetProgressWidget]:
        return list(self.query(BudgetProgressWidget))

    def _update_selection(self) -> None:
        """Update visual selection indicator and scroll into view."""
        widgets = self._get_budget_widgets()
        for i, widget in enumerate(widgets):
            if i == self._selected_idx:
                widget.add_class("budget-selected")
                widget.scroll_visible()
            else:
                widget.remove_class("budget-selected")

    def action_cursor_down(self) -> None:
        """Move selection to the next budget."""
        if not self._budget_progress:
            return
        if self._selected_idx is None:
            self._selected_idx = 0
        else:
            self._selected_idx = min(self._selected_idx + 1, len(self._budget_progress) - 1)
        self._update_selection()

    def action_cursor_up(self) -> None:
        """Move selection to the previous budget."""
        if not self._budget_progress:
            return
        if self._selected_idx is None:
            self._selected_idx = 0
        else:
            self._selected_idx = max(self._selected_idx - 1, 0)
        self._update_selection()

    def action_focus_search(self) -> None:
        self.query_one("#budget-search", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "budget-search":
            if self._search_timer:
                self._search_timer.stop()
            query = event.value.strip()
            if query:
                self._search_timer = self.set_timer(0.3, lambda: self._apply_search(query))
            else:
                self._search_query = None
                self.load_budgets()

    def _apply_search(self, query: str) -> None:
        self._search_query = query
        self.load_budgets()

    def on_key(self, event) -> None:
        """Handle Escape in search input to clear and unfocus."""
        if event.key == "escape":
            search_input = self.query_one("#budget-search", Input)
            if search_input.has_focus:
                search_input.value = ""
                self._search_query = None
                self.load_budgets()
                # Refocus the selected budget widget
                widgets = self._get_budget_widgets()
                if widgets and self._selected_idx is not None and self._selected_idx < len(widgets):
                    widgets[self._selected_idx].focus()
                event.prevent_default()

    def action_new_budget(self) -> None:
        """Show budget creation form."""
        from ledger.tui.widgets.budget_form import BudgetFormModal

        def on_budget_saved(result):
            if result:
                self.load_budgets()
                self.notify("Budget created")

        self.app.push_screen(BudgetFormModal(self.db_manager), on_budget_saved)

    def action_edit_budget(self) -> None:
        """Edit the selected budget."""
        if self._selected_idx is None or not self._budget_progress:
            self.notify("No budget selected", severity="warning")
            return

        bp = self._budget_progress[self._selected_idx]
        from ledger.tui.widgets.budget_form import BudgetFormModal

        def on_saved(result):
            if result:
                self.load_budgets()
                display_name = bp.account_name.split(":")[-1]
                self.notify(f"Budget for '{display_name}' updated")

        self.app.push_screen(BudgetFormModal(self.db_manager, budget_id=bp.budget_id), on_saved)

    def action_delete_budget(self) -> None:
        """Delete the selected budget."""
        if self._selected_idx is None or not self._budget_progress:
            self.notify("No budget selected", severity="warning")
            return

        bp = self._budget_progress[self._selected_idx]
        display_name = bp.account_name.split(":")[-1]

        from ledger.tui.widgets.confirm_dialog import ConfirmDialog

        def on_confirmed(confirmed):
            if confirmed:
                try:
                    with self.db_manager.get_session() as session:
                        BudgetService(session).delete_budget(bp.budget_id)
                    self.load_budgets()
                    self.notify(f"Budget for '{display_name}' deleted")
                except Exception as e:
                    self.notify(f"Error deleting budget: {e}", severity="error")

        self.app.push_screen(
            ConfirmDialog(f"Delete budget for '{display_name}'?"),
            on_confirmed,
        )

    def refresh_data(self) -> None:
        """Refresh budget data (common screen interface)."""
        self.load_budgets()

    def action_refresh(self) -> None:
        self.refresh_data()
