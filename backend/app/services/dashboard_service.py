"""
Dashboard service for providing aggregated financial data for the MVP frontend.

This service handles:
- Account balance calculations
- Net worth computation
- Time-series data generation
- Account ledger views
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from app.models import Account, Transaction, TransactionLine
from app.services.base_service import BaseService
from app.errors import ValidationError, BusinessLogicError


class DashboardService(BaseService):
    """Service for dashboard data aggregation and reporting."""
    
    def __init__(self, db: Session):
        super().__init__(db)
    
    def get_entity_name(self) -> str:
        return "dashboard"
    
    def get_account_balances(
        self, 
        account_ids: Optional[List[int]] = None,
        as_of_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate current balances for all accounts or specified accounts.
        
        Args:
            account_ids: Optional list of account IDs to include
            as_of_date: Optional date to calculate balances as of (YYYY-MM-DD)
            
        Returns:
            Dictionary with net worth and account balance details
        """
        self.log_operation("get_account_balances", 
                          account_ids=account_ids, as_of_date=as_of_date)
        
        # Get all accounts first
        account_query = self.db.query(Account)
        if account_ids:
            account_query = account_query.filter(Account.id.in_(account_ids))
        accounts = account_query.all()
        
        # Calculate balance for each account
        account_balances = []
        total_assets = Decimal('0')
        total_liabilities = Decimal('0')
        total_equity = Decimal('0')
        total_income = Decimal('0')
        total_expenses = Decimal('0')
        
        for account in accounts:
            # Calculate balance for this account
            from sqlalchemy import case
            
            balance_query = self.db.query(
                func.coalesce(func.sum(
                    (TransactionLine.amount * 
                     case((TransactionLine.dr_cr == 'DR', 1), else_=-1))
                ), 0)
            ).select_from(
                TransactionLine
            ).join(Transaction).filter(
                TransactionLine.account_id == account.id,
                Transaction.posted == 1
            )
            
            # Apply date filter if specified
            if as_of_date:
                balance_query = balance_query.filter(Transaction.date <= as_of_date)
            
            balance_result = balance_query.scalar()
            balance = Decimal(str(balance_result)) if balance_result else Decimal('0')
            
            # Adjust balance based on account type (assets and expenses are positive on DR side)
            if account.type in ['ASSET', 'EXPENSE']:
                adjusted_balance = balance
            else:  # LIABILITY, EQUITY, INCOME are positive on CR side
                adjusted_balance = -balance
            
            account_balances.append({
                "account_id": account.id,
                "account_name": account.name,
                "account_type": account.type,
                "currency": account.currency,
                "balance": float(adjusted_balance)
            })
            
            # Accumulate totals
            if account.type == 'ASSET':
                total_assets += adjusted_balance
            elif account.type == 'LIABILITY':
                total_liabilities += adjusted_balance
            elif account.type == 'EQUITY':
                total_equity += adjusted_balance
            elif account.type == 'INCOME':
                total_income += adjusted_balance
            elif account.type == 'EXPENSE':
                total_expenses += adjusted_balance
        
        # Net worth = Assets - Liabilities
        net_worth = total_assets - total_liabilities
        
        return {
            "net_worth": float(net_worth),
            "total_assets": float(total_assets),
            "total_liabilities": float(total_liabilities),
            "total_equity": float(total_equity),
            "total_income": float(total_income),
            "total_expenses": float(total_expenses),
            "account_balances": account_balances
        }
    
    def get_timeseries_data(
        self,
        start_date: str,
        end_date: str,
        account_ids: Optional[List[int]] = None,
        frequency: str = 'daily'
    ) -> Dict[str, Any]:
        """
        Generate time-series data for account balances.
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            account_ids: Optional list of account IDs to include
            frequency: 'daily', 'weekly', 'monthly'
            
        Returns:
            Dictionary with time-series data points and account info
        """
        self.log_operation("get_timeseries_data",
                          start_date=start_date, end_date=end_date,
                          account_ids=account_ids, frequency=frequency)
        
        # Validate date range
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError as e:
            raise ValidationError(f"Invalid date format: {str(e)}")
        
        if start_dt > end_dt:
            raise ValidationError("Start date must be before or equal to end date")
        
        # Generate date range based on frequency
        dates = self._generate_date_range(start_dt, end_dt, frequency)
        
        # Get account info for the accounts we're tracking
        account_query = self.db.query(Account.id, Account.name, Account.type)
        if account_ids:
            account_query = account_query.filter(Account.id.in_(account_ids))
        accounts = account_query.all()
        
        account_info = {
            str(acc.id): {"name": acc.name, "type": acc.type}
            for acc in accounts
        }
        
        # Calculate balances for each date
        data_points = []
        for date_point in dates:
            date_str = date_point.strftime('%Y-%m-%d')
            balances = self.get_account_balances(account_ids, date_str)
            
            # Extract account balances into a dictionary
            account_balances = {}
            for acc_balance in balances['account_balances']:
                account_balances[str(acc_balance['account_id'])] = acc_balance['balance']
            
            data_points.append({
                "date": date_str,
                "accounts": account_balances,
                "net_worth": balances['net_worth']
            })
        
        return {
            "data_points": data_points,
            "account_info": account_info
        }
    
    def get_account_ledger(
        self,
        account_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get ledger entries for a specific account in T-account format.
        
        Args:
            account_id: ID of the account
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Maximum number of entries
            offset: Number of entries to skip
            
        Returns:
            Dictionary with account info and ledger entries
        """
        self.log_operation("get_account_ledger",
                          account_id=account_id, start_date=start_date,
                          end_date=end_date, limit=limit, offset=offset)
        
        # Get account info
        account = self.db.query(Account).filter(Account.id == account_id).first()
        if not account:
            self.handle_not_found(account_id, "Account")
        
        # Build query for transaction lines
        query = self.db.query(
            TransactionLine.id,
            TransactionLine.dr_cr,
            TransactionLine.amount,
            Transaction.id.label('transaction_id'),
            Transaction.date,
            Transaction.memo,
            Transaction.type.label('transaction_type')
        ).join(Transaction).filter(
            TransactionLine.account_id == account_id,
            Transaction.posted == 1
        )
        
        # Apply date filters
        if start_date:
            query = query.filter(Transaction.date >= start_date)
        if end_date:
            query = query.filter(Transaction.date <= end_date)
        
        # Order by date descending, then by transaction ID
        query = query.order_by(Transaction.date.desc(), Transaction.id.desc())
        
        # Apply pagination
        total_query = query
        total_count = total_query.count()
        
        lines = query.offset(offset).limit(limit).all()
        
        # Calculate running balance
        # For this simple implementation, we'll calculate current balance
        current_balance_data = self.get_account_balances([account_id])
        current_balance = next(
            (acc['balance'] for acc in current_balance_data['account_balances'] 
             if acc['account_id'] == account_id), 
            0.0
        )
        
        # Format ledger entries
        ledger_entries = []
        running_balance = current_balance
        
        for line in lines:
            # Adjust amount based on account type and dr/cr
            if account.type in ['ASSET', 'EXPENSE']:
                # For assets and expenses, DR increases balance, CR decreases
                amount_effect = float(line.amount) if line.dr_cr == 'DR' else -float(line.amount)
            else:
                # For liabilities, equity, income, CR increases balance, DR decreases
                amount_effect = float(line.amount) if line.dr_cr == 'CR' else -float(line.amount)
            
            ledger_entries.append({
                "transaction_id": line.transaction_id,
                "transaction_line_id": line.id,
                "date": line.date,
                "memo": line.memo,
                "transaction_type": line.transaction_type,
                "side": line.dr_cr,
                "amount": float(line.amount),
                "running_balance": running_balance
            })
            
            # Update running balance (going backwards in time)
            running_balance -= amount_effect
        
        return {
            "account": {
                "id": account.id,
                "name": account.name,
                "type": account.type,
                "currency": account.currency,
                "current_balance": current_balance
            },
            "ledger_entries": ledger_entries,
            "total_entries": total_count,
            "has_more": (offset + limit) < total_count
        }
    
    def _generate_date_range(self, start_date: date, end_date: date, frequency: str) -> List[date]:
        """Generate a list of dates based on frequency."""
        from datetime import timedelta
        
        dates = []
        current_date = start_date
        
        if frequency == 'daily':
            delta = timedelta(days=1)
        elif frequency == 'weekly':
            delta = timedelta(weeks=1)
        elif frequency == 'monthly':
            # For monthly, we'll approximate with 30 days
            delta = timedelta(days=30)
        else:
            raise ValidationError(f"Invalid frequency: {frequency}")
        
        while current_date <= end_date:
            dates.append(current_date)
            current_date += delta
        
        # Always include the end date if it's not already included
        if dates and dates[-1] != end_date:
            dates.append(end_date)
        
        return dates