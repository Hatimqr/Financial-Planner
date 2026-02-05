"""Report service for generating financial reports and KPIs."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from ledger.db.models import Account, Entry, Posting
from ledger.repositories.account import AccountRepository
from ledger.repositories.entry import EntryRepository
from ledger.repositories.posting import PostingRepository


@dataclass
class AccountBalance:
    """Balance information for an account."""

    account_id: int
    account_name: str
    account_type: str
    balance: Decimal
    is_placeholder: bool


@dataclass
class PeriodSummary:
    """Summary of income and expenses for a period."""

    start_date: date
    end_date: date
    total_income: Decimal
    total_expenses: Decimal
    net_income: Decimal
    savings_rate: Decimal  # As percentage (0-100)


@dataclass
class NetWorthSummary:
    """Net worth breakdown."""

    total_assets: Decimal
    total_liabilities: Decimal
    net_worth: Decimal
    asset_accounts: List[AccountBalance]
    liability_accounts: List[AccountBalance]


@dataclass
class CategoryBreakdown:
    """Spending/income breakdown by category."""

    category_name: str
    amount: Decimal
    percentage: Decimal  # As percentage of total (0-100)
    subcategories: List["CategoryBreakdown"]


@dataclass
class RecentTransaction:
    """Simplified transaction for display."""

    id: int
    date: date
    description: str
    payee: Optional[str]
    primary_account: str
    amount: Decimal
    is_expense: bool


class ReportService:
    """Service for generating financial reports."""

    def __init__(self, session: Session):
        """Initialize report service."""
        self.session = session
        self.account_repo = AccountRepository(session)
        self.entry_repo = EntryRepository(session)
        self.posting_repo = PostingRepository(session)

    def get_net_worth(self) -> NetWorthSummary:
        """
        Calculate current net worth.

        Returns:
            NetWorthSummary with asset and liability breakdowns
        """
        # Get all asset accounts
        asset_accounts = self.account_repo.get_by_type("asset")
        liability_accounts = self.account_repo.get_by_type("liability")

        asset_balances = []
        total_assets = Decimal("0")

        for account in asset_accounts:
            balance = self.posting_repo.get_account_balance(account.id)
            asset_balances.append(
                AccountBalance(
                    account_id=account.id,
                    account_name=account.name,
                    account_type=account.type,
                    balance=balance,
                    is_placeholder=account.is_placeholder,
                )
            )
            if not account.is_placeholder:
                total_assets += balance

        liability_balances = []
        total_liabilities = Decimal("0")

        for account in liability_accounts:
            balance = self.posting_repo.get_account_balance(account.id)
            liability_balances.append(
                AccountBalance(
                    account_id=account.id,
                    account_name=account.name,
                    account_type=account.type,
                    balance=balance,
                    is_placeholder=account.is_placeholder,
                )
            )
            if not account.is_placeholder:
                # Liabilities typically have negative balances (credits)
                total_liabilities += abs(balance)

        return NetWorthSummary(
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            net_worth=total_assets - total_liabilities,
            asset_accounts=asset_balances,
            liability_accounts=liability_balances,
        )

    def get_period_summary(
        self, start_date: date, end_date: date
    ) -> PeriodSummary:
        """
        Calculate income, expenses, and savings for a period.

        Args:
            start_date: Period start date (inclusive)
            end_date: Period end date (inclusive)

        Returns:
            PeriodSummary with totals and savings rate
        """
        # Query for income (negative postings to income accounts)
        income_query = (
            self.session.query(func.sum(Posting.amount))
            .join(Entry)
            .join(Account)
            .filter(
                Entry.date >= start_date,
                Entry.date <= end_date,
                Account.type == "income",
            )
        )
        total_income_raw = income_query.scalar() or Decimal("0")
        # Income postings are negative (credits), so negate to get positive income
        total_income = abs(Decimal(str(total_income_raw)))

        # Query for expenses (positive postings to expense accounts)
        expense_query = (
            self.session.query(func.sum(Posting.amount))
            .join(Entry)
            .join(Account)
            .filter(
                Entry.date >= start_date,
                Entry.date <= end_date,
                Account.type == "expense",
            )
        )
        total_expenses_raw = expense_query.scalar() or Decimal("0")
        total_expenses = Decimal(str(total_expenses_raw))

        net_income = total_income - total_expenses

        # Calculate savings rate
        if total_income > 0:
            savings_rate = (net_income / total_income) * 100
        else:
            savings_rate = Decimal("0")

        return PeriodSummary(
            start_date=start_date,
            end_date=end_date,
            total_income=total_income,
            total_expenses=total_expenses,
            net_income=net_income,
            savings_rate=savings_rate.quantize(Decimal("0.1")),
        )

    def get_current_month_summary(self) -> PeriodSummary:
        """Get summary for current month."""
        today = date.today()
        start_of_month = today.replace(day=1)
        return self.get_period_summary(start_of_month, today)

    def get_previous_month_summary(self) -> PeriodSummary:
        """Get summary for previous month."""
        today = date.today()
        first_of_current = today.replace(day=1)
        last_of_previous = first_of_current - timedelta(days=1)
        first_of_previous = last_of_previous.replace(day=1)
        return self.get_period_summary(first_of_previous, last_of_previous)

    def get_expense_breakdown(
        self, start_date: date, end_date: date
    ) -> List[CategoryBreakdown]:
        """
        Get expense breakdown by category for a period.

        Args:
            start_date: Period start date
            end_date: Period end date

        Returns:
            List of category breakdowns with percentages
        """
        # Query expenses grouped by top-level category
        expense_query = (
            self.session.query(Account.name, func.sum(Posting.amount))
            .join(Posting)
            .join(Entry)
            .filter(
                Entry.date >= start_date,
                Entry.date <= end_date,
                Account.type == "expense",
                Account.is_placeholder.is_(False),
            )
            .group_by(Account.name)
            .all()
        )

        # Calculate total for percentages
        total = sum(abs(Decimal(str(amt))) for _, amt in expense_query)

        breakdowns = []
        for account_name, amount in expense_query:
            amt = abs(Decimal(str(amount)))
            percentage = (amt / total * 100) if total > 0 else Decimal("0")
            breakdowns.append(
                CategoryBreakdown(
                    category_name=account_name,
                    amount=amt,
                    percentage=percentage.quantize(Decimal("0.1")),
                    subcategories=[],
                )
            )

        # Sort by amount descending
        breakdowns.sort(key=lambda x: x.amount, reverse=True)
        return breakdowns

    def get_income_breakdown(
        self, start_date: date, end_date: date
    ) -> List[CategoryBreakdown]:
        """
        Get income breakdown by category for a period.

        Args:
            start_date: Period start date
            end_date: Period end date

        Returns:
            List of category breakdowns with percentages
        """
        income_query = (
            self.session.query(Account.name, func.sum(Posting.amount))
            .join(Posting)
            .join(Entry)
            .filter(
                Entry.date >= start_date,
                Entry.date <= end_date,
                Account.type == "income",
                Account.is_placeholder.is_(False),
            )
            .group_by(Account.name)
            .all()
        )

        # Income postings are negative, so use abs
        total = sum(abs(Decimal(str(amt))) for _, amt in income_query)

        breakdowns = []
        for account_name, amount in income_query:
            amt = abs(Decimal(str(amount)))
            percentage = (amt / total * 100) if total > 0 else Decimal("0")
            breakdowns.append(
                CategoryBreakdown(
                    category_name=account_name,
                    amount=amt,
                    percentage=percentage.quantize(Decimal("0.1")),
                    subcategories=[],
                )
            )

        breakdowns.sort(key=lambda x: x.amount, reverse=True)
        return breakdowns

    def get_recent_transactions(self, limit: int = 10) -> List[RecentTransaction]:
        """
        Get recent transactions formatted for display.

        Args:
            limit: Number of transactions to return

        Returns:
            List of recent transactions
        """
        entries = self.entry_repo.get_recent(limit)
        transactions = []

        for entry in entries:
            # Get postings for this entry
            postings = self.posting_repo.get_by_entry(entry.id)

            # Find the primary account (expense or income for display)
            primary_posting = None
            for posting in postings:
                account = self.account_repo.get_by_id(posting.account_id)
                if account and account.type in ("expense", "income"):
                    primary_posting = posting
                    break

            # Fallback to first posting if no expense/income found
            if not primary_posting and postings:
                primary_posting = postings[0]

            if primary_posting:
                account = self.account_repo.get_by_id(primary_posting.account_id)
                is_expense = account.type == "expense" if account else False

                transactions.append(
                    RecentTransaction(
                        id=entry.id,
                        date=entry.date,
                        description=entry.description,
                        payee=entry.payee,
                        primary_account=account.name if account else "Unknown",
                        amount=abs(primary_posting.amount),
                        is_expense=is_expense,
                    )
                )

        return transactions

    def get_income_statement(
        self, start_date: date, end_date: date
    ) -> Dict[str, List[Tuple[str, Decimal]]]:
        """
        Generate income statement (P&L) for a period.

        Args:
            start_date: Period start date
            end_date: Period end date

        Returns:
            Dict with 'income' and 'expenses' lists of (account_name, amount) tuples
        """
        income_breakdown = self.get_income_breakdown(start_date, end_date)
        expense_breakdown = self.get_expense_breakdown(start_date, end_date)

        return {
            "income": [(b.category_name, b.amount) for b in income_breakdown],
            "expenses": [(b.category_name, b.amount) for b in expense_breakdown],
            "total_income": sum(b.amount for b in income_breakdown),
            "total_expenses": sum(b.amount for b in expense_breakdown),
            "net_income": sum(b.amount for b in income_breakdown)
            - sum(b.amount for b in expense_breakdown),
        }

    def get_balance_sheet(self) -> Dict[str, any]:
        """
        Generate balance sheet (snapshot of current financial position).

        Returns:
            Dict with assets, liabilities, equity, and net worth
        """
        net_worth = self.get_net_worth()

        # Get equity accounts
        equity_accounts = self.account_repo.get_by_type("equity")
        equity_balances = []
        total_equity = Decimal("0")

        for account in equity_accounts:
            balance = self.posting_repo.get_account_balance(account.id)
            if not account.is_placeholder:
                equity_balances.append((account.name, abs(balance)))
                total_equity += abs(balance)

        return {
            "assets": [
                (ab.account_name, ab.balance)
                for ab in net_worth.asset_accounts
                if not ab.is_placeholder
            ],
            "liabilities": [
                (ab.account_name, abs(ab.balance))
                for ab in net_worth.liability_accounts
                if not ab.is_placeholder
            ],
            "equity": equity_balances,
            "total_assets": net_worth.total_assets,
            "total_liabilities": net_worth.total_liabilities,
            "total_equity": total_equity,
            "net_worth": net_worth.net_worth,
        }

    def search_transactions(
        self,
        query: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 50,
    ) -> List[Entry]:
        """
        Search transactions by description or payee.

        Args:
            query: Search query string
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Maximum results

        Returns:
            List of matching entries
        """
        search_query = (
            self.session.query(Entry)
            .filter(
                (Entry.description.ilike(f"%{query}%"))
                | (Entry.payee.ilike(f"%{query}%"))
            )
        )

        if start_date:
            search_query = search_query.filter(Entry.date >= start_date)
        if end_date:
            search_query = search_query.filter(Entry.date <= end_date)

        return (
            search_query.order_by(Entry.date.desc())
            .limit(limit)
            .all()
        )
