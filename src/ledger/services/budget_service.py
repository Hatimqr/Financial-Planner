"""Budget service for managing budgets and tracking spending."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ledger.db.models import Budget, Entry, Posting
from ledger.repositories.account import AccountRepository


@dataclass
class BudgetProgress:
    """Budget progress information."""

    budget_id: int
    account_id: int
    account_name: str
    budgeted_amount: Decimal
    spent_amount: Decimal
    remaining_amount: Decimal
    percentage_used: Decimal  # 0-100+
    is_over_budget: bool


class BudgetService:
    """Service for budget management and tracking."""

    VALID_PERIODS = ["monthly", "quarterly", "yearly"]

    def __init__(self, session: Session):
        """Initialize budget service."""
        self.session = session
        self.account_repo = AccountRepository(session)

    def create_budget(
        self,
        account_id: int,
        amount: Decimal,
        period: str = "monthly",
        effective_from: Optional[date] = None,
        effective_to: Optional[date] = None,
    ) -> Budget:
        """
        Create a new budget for an account.

        Args:
            account_id: Account to budget
            amount: Budget amount
            period: Budget period (monthly, quarterly, yearly)
            effective_from: Start date (defaults to start of current month)
            effective_to: End date (optional)

        Returns:
            Created budget

        Raises:
            ValueError: If validation fails
        """
        if period not in self.VALID_PERIODS:
            raise ValueError(f"Invalid period '{period}'. Must be one of: {self.VALID_PERIODS}")

        account = self.account_repo.get_by_id(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")

        if account.type != "expense":
            raise ValueError("Budgets can only be created for expense accounts")

        if effective_from is None:
            effective_from = date.today().replace(day=1)

        budget = Budget(
            account_id=account_id,
            amount=amount,
            period=period,
            effective_from=effective_from,
            effective_to=effective_to,
        )
        self.session.add(budget)
        self.session.flush()
        return budget

    def get_budget_by_id(self, budget_id: int) -> Optional[Budget]:
        """Get budget by ID."""
        return self.session.query(Budget).filter_by(id=budget_id).first()

    def get_budgets_for_account(self, account_id: int) -> List[Budget]:
        """Get all budgets for an account."""
        return (
            self.session.query(Budget)
            .filter_by(account_id=account_id)
            .order_by(Budget.effective_from.desc())
            .all()
        )

    def get_active_budgets(self, as_of_date: Optional[date] = None) -> List[Budget]:
        """
        Get all currently active budgets.

        Args:
            as_of_date: Date to check (defaults to today)

        Returns:
            List of active budgets
        """
        if as_of_date is None:
            as_of_date = date.today()

        return (
            self.session.query(Budget)
            .filter(
                Budget.effective_from <= as_of_date,
                (Budget.effective_to.is_(None)) | (Budget.effective_to >= as_of_date),
            )
            .all()
        )

    def get_spending_for_period(
        self, account_id: int, start_date: date, end_date: date
    ) -> Decimal:
        """
        Get total spending for an account in a period.

        Args:
            account_id: Account to check
            start_date: Period start
            end_date: Period end

        Returns:
            Total spending (positive value)
        """
        result = (
            self.session.query(func.sum(Posting.amount))
            .join(Entry)
            .filter(
                Posting.account_id == account_id,
                Entry.date >= start_date,
                Entry.date <= end_date,
            )
            .scalar()
        )
        return Decimal(str(result)) if result else Decimal("0")

    def get_budget_progress(
        self, budget: Budget, as_of_date: Optional[date] = None
    ) -> BudgetProgress:
        """
        Calculate progress for a budget.

        Args:
            budget: Budget to check
            as_of_date: Date to calculate through (defaults to today)

        Returns:
            BudgetProgress with spending details
        """
        if as_of_date is None:
            as_of_date = date.today()

        # Calculate period dates based on budget period
        start_date, end_date = self._get_period_dates(budget.period, as_of_date)

        # Get spending for this period
        spent = self.get_spending_for_period(budget.account_id, start_date, end_date)

        # Calculate progress
        remaining = budget.amount - spent
        if budget.amount > 0:
            percentage = (spent / budget.amount) * 100
        else:
            percentage = Decimal("0")

        # Get account name
        account = self.account_repo.get_by_id(budget.account_id)
        account_name = account.name if account else "Unknown"

        return BudgetProgress(
            budget_id=budget.id,
            account_id=budget.account_id,
            account_name=account_name,
            budgeted_amount=budget.amount,
            spent_amount=spent,
            remaining_amount=remaining,
            percentage_used=percentage.quantize(Decimal("0.1")),
            is_over_budget=spent > budget.amount,
        )

    def get_all_budget_progress(
        self, as_of_date: Optional[date] = None
    ) -> List[BudgetProgress]:
        """
        Get progress for all active budgets.

        Args:
            as_of_date: Date to calculate through

        Returns:
            List of BudgetProgress for all active budgets
        """
        budgets = self.get_active_budgets(as_of_date)
        return [self.get_budget_progress(b, as_of_date) for b in budgets]

    def _get_period_dates(self, period: str, as_of_date: date) -> tuple[date, date]:
        """Get start and end dates for a budget period."""
        if period == "monthly":
            start = as_of_date.replace(day=1)
            # End of month
            if as_of_date.month == 12:
                end = as_of_date.replace(year=as_of_date.year + 1, month=1, day=1)
            else:
                end = as_of_date.replace(month=as_of_date.month + 1, day=1)
            from datetime import timedelta
            end = end - timedelta(days=1)
        elif period == "quarterly":
            quarter = (as_of_date.month - 1) // 3
            start = as_of_date.replace(month=quarter * 3 + 1, day=1)
            end_month = quarter * 3 + 3
            if end_month > 12:
                end = as_of_date.replace(year=as_of_date.year + 1, month=1, day=1)
            else:
                end = as_of_date.replace(month=end_month + 1, day=1)
            from datetime import timedelta
            end = end - timedelta(days=1)
        elif period == "yearly":
            start = as_of_date.replace(month=1, day=1)
            end = as_of_date.replace(month=12, day=31)
        else:
            start = as_of_date.replace(day=1)
            end = as_of_date

        return start, end

    def update_budget(
        self,
        budget_id: int,
        amount: Optional[Decimal] = None,
        effective_to: Optional[date] = None,
    ) -> Budget:
        """
        Update a budget.

        Args:
            budget_id: Budget ID
            amount: New amount (optional)
            effective_to: New end date (optional)

        Returns:
            Updated budget

        Raises:
            ValueError: If budget not found
        """
        budget = self.get_budget_by_id(budget_id)
        if not budget:
            raise ValueError(f"Budget {budget_id} not found")

        if amount is not None:
            budget.amount = amount
        if effective_to is not None:
            budget.effective_to = effective_to

        self.session.flush()
        return budget

    def delete_budget(self, budget_id: int) -> None:
        """
        Delete a budget.

        Args:
            budget_id: Budget ID

        Raises:
            ValueError: If budget not found
        """
        budget = self.get_budget_by_id(budget_id)
        if not budget:
            raise ValueError(f"Budget {budget_id} not found")

        self.session.delete(budget)
        self.session.flush()
