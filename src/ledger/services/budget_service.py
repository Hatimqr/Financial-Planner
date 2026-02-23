"""Budget service for managing budgets and tracking spending."""

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ledger.db.models import Budget, Entry, Posting
from ledger.repositories.account import AccountRepository

_PERIOD_ABBREV = {"monthly": "mo", "quarterly": "qtr", "yearly": "yr"}
_PERIOD_MONTHS = {"monthly": 1, "quarterly": 3, "yearly": 12}


@dataclass
class BudgetProgress:
    """Budget progress information."""

    budget_id: int
    account_id: int
    account_name: str
    budgeted_amount: Decimal  # pro-rated amount for the view window
    spent_amount: Decimal
    remaining_amount: Decimal
    percentage_used: Decimal  # 0-100+
    is_over_budget: bool
    period: str = "monthly"
    is_prorated: bool = False
    prorate_label: str = ""
    rate_amount: Decimal = field(default_factory=lambda: Decimal("0"))
    rate_period: str = ""


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
        Get total spending for an account (and its children) in a period.

        Args:
            account_id: Account to check
            start_date: Period start
            end_date: Period end

        Returns:
            Total spending (positive value)
        """
        from ledger.db.models import Account

        account = self.account_repo.get_by_id(account_id)
        if not account:
            return Decimal("0")

        # Collect account IDs: this account + all descendants
        account_ids = [account_id]
        children = self.account_repo.get_children(account.name)
        account_ids.extend(c.id for c in children)

        result = (
            self.session.query(func.sum(Posting.amount))
            .join(Entry)
            .filter(
                Posting.account_id.in_(account_ids),
                Entry.date >= start_date,
                Entry.date <= end_date,
            )
            .scalar()
        )
        return Decimal(str(result)) if result else Decimal("0")

    def get_budget_progress(
        self,
        budget: Budget,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> BudgetProgress:
        """
        Calculate progress for a budget within a view window.

        When start_date/end_date are provided, the budget amount is pro-rated
        to match the view window. Otherwise falls back to the budget's own period.
        """
        if start_date is None or end_date is None:
            as_of = end_date or date.today()
            start_date, end_date = self._get_period_dates(budget.period, as_of)

        prorated, is_prorated, label = self._prorate_budget_amount(
            budget.period, budget.amount, start_date, end_date
        )

        spent = self.get_spending_for_period(budget.account_id, start_date, end_date)

        remaining = prorated - spent
        if prorated > 0:
            percentage = (spent / prorated) * 100
        else:
            percentage = Decimal("0")

        account = self.account_repo.get_by_id(budget.account_id)
        account_name = account.name if account else "Unknown"

        return BudgetProgress(
            budget_id=budget.id,
            account_id=budget.account_id,
            account_name=account_name,
            budgeted_amount=prorated,
            spent_amount=spent,
            remaining_amount=remaining,
            percentage_used=percentage.quantize(Decimal("0.1")),
            is_over_budget=spent > prorated,
            period=budget.period,
            is_prorated=is_prorated,
            prorate_label=label,
            rate_amount=budget.amount,
            rate_period=budget.period,
        )

    def get_all_budget_progress(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[BudgetProgress]:
        """
        Get progress for all active budgets within a view window.

        Budgets are considered active if they overlap with the view window.
        """
        if start_date is not None and end_date is not None:
            # Budgets are rates — show any budget not yet ended.
            # Only effective_to gates visibility (budget was explicitly closed).
            budgets = (
                self.session.query(Budget)
                .filter(
                    (Budget.effective_to.is_(None)) | (Budget.effective_to >= start_date),
                )
                .all()
            )
        else:
            budgets = self.get_active_budgets()
        return [self.get_budget_progress(b, start_date, end_date) for b in budgets]

    def _get_period_dates(self, period: str, as_of_date: date) -> tuple[date, date]:
        """Get start and end dates for a budget period."""
        if period == "monthly":
            start = as_of_date.replace(day=1)
            if as_of_date.month == 12:
                end = as_of_date.replace(year=as_of_date.year + 1, month=1, day=1)
            else:
                end = as_of_date.replace(month=as_of_date.month + 1, day=1)
            end = end - timedelta(days=1)
        elif period == "quarterly":
            quarter = (as_of_date.month - 1) // 3
            start = as_of_date.replace(month=quarter * 3 + 1, day=1)
            end_month = quarter * 3 + 3
            if end_month >= 12:
                end = as_of_date.replace(year=as_of_date.year + 1, month=1, day=1)
            else:
                end = as_of_date.replace(month=end_month + 1, day=1)
            end = end - timedelta(days=1)
        elif period == "yearly":
            start = as_of_date.replace(month=1, day=1)
            end = as_of_date.replace(month=12, day=31)
        else:
            start = as_of_date.replace(day=1)
            end = as_of_date

        return start, end

    @staticmethod
    def _detect_whole_months(start: date, end: date) -> Optional[int]:
        """
        Return the number of whole calendar months if the range is
        first-of-month to last-of-month, else None.
        """
        if start.day != 1:
            return None

        last_day_of_end_month = calendar.monthrange(end.year, end.month)[1]
        if end.day != last_day_of_end_month:
            return None

        return (end.year - start.year) * 12 + (end.month - start.month) + 1

    @staticmethod
    def _prorate_budget_amount(
        budget_period: str,
        budget_amount: Decimal,
        view_start: date,
        view_end: date,
    ) -> tuple[Decimal, bool, str]:
        """
        Pro-rate a budget amount from its natural period to a view window.

        Returns (prorated_amount, is_prorated, label).
        """
        period_months = _PERIOD_MONTHS.get(budget_period, 1)
        abbrev = _PERIOD_ABBREV.get(budget_period, budget_period)

        whole_months = BudgetService._detect_whole_months(view_start, view_end)

        if whole_months is not None:
            # Calendar-aware scaling
            if whole_months == period_months:
                # Exact match — no pro-rating needed
                return budget_amount, False, ""

            scale = Decimal(str(whole_months)) / Decimal(str(period_months))
            prorated = (budget_amount * scale).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            # Build label
            if whole_months > period_months:
                multiplier = whole_months // period_months
                if whole_months % period_months == 0 and multiplier > 1:
                    label = f"AED {budget_amount:,.2f}/{abbrev} \u00d7 {multiplier} {abbrev}"
                else:
                    label = f"AED {budget_amount:,.2f}/{abbrev} \u00d7 {whole_months}/{period_months} mo"
            else:
                divisor = period_months // whole_months
                if period_months % whole_months == 0 and divisor > 1:
                    label = f"AED {budget_amount:,.2f}/{abbrev} \u00f7 {divisor}"
                else:
                    label = f"AED {budget_amount:,.2f}/{abbrev} \u00d7 {whole_months}/{period_months} mo"

            return prorated, True, label

        # Irregular window — day-based pro-rating
        view_days = (view_end - view_start).days + 1

        # Approximate period days
        if budget_period == "monthly":
            period_days = Decimal("30.4375")
        elif budget_period == "quarterly":
            period_days = Decimal("91.3125")
        elif budget_period == "yearly":
            period_days = Decimal("365.25")
        else:
            period_days = Decimal("30.4375")

        scale = Decimal(str(view_days)) / period_days
        prorated = (budget_amount * scale).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        label = f"AED {budget_amount:,.2f}/{abbrev} pro-rated to {view_days} days"

        return prorated, True, label

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

    def get_overall_budget_utilization(
        self, start_date: date, end_date: date
    ) -> Decimal:
        """
        Calculate overall budget utilization percentage across all active budgets.

        Pro-rates each budget amount to match the view window before summing.

        Returns:
            Decimal 0-100+ representing percentage of total budget used
        """
        progress_list = self.get_all_budget_progress(start_date, end_date)
        if not progress_list:
            return Decimal("0")

        total_budgeted = sum(p.budgeted_amount for p in progress_list)
        total_spent = sum(p.spent_amount for p in progress_list)

        if total_budgeted == 0:
            return Decimal("0")

        return ((total_spent / total_budgeted) * 100).quantize(Decimal("0.1"))

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
