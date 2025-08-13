"""
Tests for the dashboard service functionality.
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from app.services.dashboard_service import DashboardService
from app.services.transaction_service import TransactionService
from app.models import Account, Transaction, TransactionLine
from app.errors import ValidationError, NotFoundError


class TestDashboardService:
    """Test suite for DashboardService."""

    @pytest.fixture
    def dashboard_service(self, db_session):
        """Create a dashboard service instance."""
        return DashboardService(db_session)

    @pytest.fixture
    def transaction_service(self, db_session):
        """Create a transaction service instance."""
        return TransactionService(db_session)

    @pytest.fixture
    def accounts_with_data(self, db_session, transaction_service):
        """Create accounts with sample transaction data."""
        # Create accounts
        checking = Account(name="Checking Account", type="ASSET", currency="USD")
        savings = Account(name="Savings Account", type="ASSET", currency="USD")
        credit_card = Account(name="Credit Card", type="LIABILITY", currency="USD")
        salary_income = Account(name="Salary Income", type="INCOME", currency="USD")
        food_expense = Account(name="Food Expense", type="EXPENSE", currency="USD")
        
        db_session.add_all([checking, savings, credit_card, salary_income, food_expense])
        db_session.flush()
        
        # Create sample transactions
        today = date.today()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)
        
        # Transaction 1: Salary deposit (week ago)
        transaction_service.create_transaction(
            transaction_type='TRANSFER',
            date=week_ago.isoformat(),
            memo='Salary deposit',
            lines=[
                {'account_id': checking.id, 'dr_cr': 'DR', 'amount': Decimal('5000.00')},
                {'account_id': salary_income.id, 'dr_cr': 'CR', 'amount': Decimal('5000.00')}
            ]
        )
        
        # Transaction 2: Transfer to savings (yesterday)
        transaction_service.create_transaction(
            transaction_type='TRANSFER',
            date=yesterday.isoformat(),
            memo='Transfer to savings',
            lines=[
                {'account_id': checking.id, 'dr_cr': 'CR', 'amount': Decimal('2000.00')},
                {'account_id': savings.id, 'dr_cr': 'DR', 'amount': Decimal('2000.00')}
            ]
        )
        
        # Transaction 3: Credit card purchase (today)
        transaction_service.create_transaction(
            transaction_type='TRANSFER',
            date=today.isoformat(),
            memo='Grocery shopping',
            lines=[
                {'account_id': food_expense.id, 'dr_cr': 'DR', 'amount': Decimal('150.00')},
                {'account_id': credit_card.id, 'dr_cr': 'CR', 'amount': Decimal('150.00')}
            ]
        )
        
        # Post all transactions
        transactions = db_session.query(Transaction).all()
        for tx in transactions:
            transaction_service.post_transaction(tx.id)
        
        return {
            'checking': checking,
            'savings': savings,
            'credit_card': credit_card,
            'salary_income': salary_income,
            'food_expense': food_expense
        }

    def test_get_account_balances_all_accounts(self, dashboard_service, accounts_with_data):
        """Test getting balances for all accounts."""
        result = dashboard_service.get_account_balances()
        
        # Check net worth calculation (Assets - Liabilities)
        # Assets: Checking (3000) + Savings (2000) = 5000
        # Liabilities: Credit Card (150) = 150
        # Net worth: 5000 - 150 = 4850
        assert result['net_worth'] == 4850.0
        assert result['total_assets'] == 5000.0
        assert result['total_liabilities'] == 150.0
        assert result['total_income'] == 5000.0
        assert result['total_expenses'] == 150.0
        
        # Check individual account balances
        account_balances = {acc['account_name']: acc['balance'] for acc in result['account_balances']}
        assert account_balances['Checking Account'] == 3000.0  # 5000 - 2000
        assert account_balances['Savings Account'] == 2000.0
        assert account_balances['Credit Card'] == 150.0
        assert account_balances['Salary Income'] == 5000.0
        assert account_balances['Food Expense'] == 150.0

    def test_get_account_balances_filtered_accounts(self, dashboard_service, accounts_with_data):
        """Test getting balances for specific accounts only."""
        checking_id = accounts_with_data['checking'].id
        savings_id = accounts_with_data['savings'].id
        
        result = dashboard_service.get_account_balances(account_ids=[checking_id, savings_id])
        
        # Should only include checking and savings
        assert len(result['account_balances']) == 2
        account_names = {acc['account_name'] for acc in result['account_balances']}
        assert account_names == {'Checking Account', 'Savings Account'}
        
        # Net worth should only consider these accounts
        assert result['net_worth'] == 5000.0  # Only assets, no liabilities included
        assert result['total_assets'] == 5000.0
        assert result['total_liabilities'] == 0.0

    def test_get_account_balances_as_of_date(self, dashboard_service, accounts_with_data):
        """Test getting balances as of a specific date."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        
        result = dashboard_service.get_account_balances(as_of_date=yesterday)
        
        # As of yesterday, only salary and transfer to savings should be included
        # Checking: 5000 - 2000 = 3000
        # Savings: 2000
        # Credit card purchase not included (happened today)
        account_balances = {acc['account_name']: acc['balance'] for acc in result['account_balances']}
        assert account_balances['Checking Account'] == 3000.0
        assert account_balances['Savings Account'] == 2000.0
        assert account_balances.get('Credit Card', 0.0) == 0.0  # No balance yet
        assert account_balances.get('Food Expense', 0.0) == 0.0  # No expense yet

    def test_get_timeseries_data_daily(self, dashboard_service, accounts_with_data):
        """Test getting daily time-series data."""
        start_date = (date.today() - timedelta(days=7)).isoformat()
        end_date = date.today().isoformat()
        
        result = dashboard_service.get_timeseries_data(
            start_date=start_date,
            end_date=end_date,
            frequency='daily'
        )
        
        # Should have data points for the date range
        assert len(result['data_points']) >= 3  # At least start, some middle, end
        
        # Check account info structure
        assert 'account_info' in result
        assert len(result['account_info']) == 5  # All accounts
        
        # Check data point structure
        data_point = result['data_points'][0]
        assert 'date' in data_point
        assert 'accounts' in data_point
        assert 'net_worth' in data_point
        
        # Check that balances change over time
        first_point = result['data_points'][0]
        last_point = result['data_points'][-1]
        
        # Net worth should be different at start vs end
        assert first_point['net_worth'] != last_point['net_worth']

    def test_get_timeseries_data_filtered_accounts(self, dashboard_service, accounts_with_data):
        """Test getting time-series data for specific accounts only."""
        checking_id = accounts_with_data['checking'].id
        start_date = (date.today() - timedelta(days=7)).isoformat()
        end_date = date.today().isoformat()
        
        result = dashboard_service.get_timeseries_data(
            start_date=start_date,
            end_date=end_date,
            account_ids=[checking_id],
            frequency='daily'
        )
        
        # Should only include checking account
        assert len(result['account_info']) == 1
        assert str(checking_id) in result['account_info']
        
        # Data points should only have checking account data
        for data_point in result['data_points']:
            assert str(checking_id) in data_point['accounts']
            # Should only have one account in the accounts dict
            assert len(data_point['accounts']) == 1

    def test_get_timeseries_data_invalid_dates(self, dashboard_service):
        """Test time-series data with invalid date formats."""
        with pytest.raises(ValidationError, match="Invalid date format"):
            dashboard_service.get_timeseries_data(
                start_date="invalid-date",
                end_date="2024-01-01",
                frequency='daily'
            )

    def test_get_timeseries_data_start_after_end(self, dashboard_service):
        """Test time-series data with start date after end date."""
        with pytest.raises(ValidationError, match="Start date must be before"):
            dashboard_service.get_timeseries_data(
                start_date="2024-01-02",
                end_date="2024-01-01",
                frequency='daily'
            )

    def test_get_account_ledger_basic(self, dashboard_service, accounts_with_data):
        """Test getting account ledger for a specific account."""
        checking_id = accounts_with_data['checking'].id
        
        result = dashboard_service.get_account_ledger(account_id=checking_id)
        
        # Check account info
        assert result['account']['id'] == checking_id
        assert result['account']['name'] == 'Checking Account'
        assert result['account']['type'] == 'ASSET'
        assert result['account']['current_balance'] == 3000.0
        
        # Check ledger entries
        assert len(result['ledger_entries']) == 2  # Salary deposit + transfer out
        assert result['total_entries'] == 2
        assert result['has_more'] is False
        
        # Check entry structure
        entry = result['ledger_entries'][0]
        assert 'transaction_id' in entry
        assert 'transaction_line_id' in entry
        assert 'date' in entry
        assert 'memo' in entry
        assert 'side' in entry
        assert 'amount' in entry
        assert 'running_balance' in entry

    def test_get_account_ledger_with_date_filter(self, dashboard_service, accounts_with_data):
        """Test getting account ledger with date filtering."""
        checking_id = accounts_with_data['checking'].id
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        
        result = dashboard_service.get_account_ledger(
            account_id=checking_id,
            start_date=yesterday
        )
        
        # Should only include transfer transaction (from yesterday)
        assert len(result['ledger_entries']) == 1
        assert result['ledger_entries'][0]['memo'] == 'Transfer to savings'

    def test_get_account_ledger_with_pagination(self, dashboard_service, accounts_with_data):
        """Test account ledger with pagination."""
        checking_id = accounts_with_data['checking'].id
        
        # Get first page with limit 1
        result = dashboard_service.get_account_ledger(
            account_id=checking_id,
            limit=1,
            offset=0
        )
        
        assert len(result['ledger_entries']) == 1
        assert result['total_entries'] == 2
        assert result['has_more'] is True
        
        # Get second page
        result_page2 = dashboard_service.get_account_ledger(
            account_id=checking_id,
            limit=1,
            offset=1
        )
        
        assert len(result_page2['ledger_entries']) == 1
        assert result_page2['total_entries'] == 2
        assert result_page2['has_more'] is False

    def test_get_account_ledger_nonexistent_account(self, dashboard_service):
        """Test getting ledger for non-existent account."""
        with pytest.raises(NotFoundError):
            dashboard_service.get_account_ledger(account_id=99999)

    def test_get_account_balances_empty_database(self, dashboard_service):
        """Test getting balances when no accounts exist."""
        result = dashboard_service.get_account_balances()
        
        assert result['net_worth'] == 0.0
        assert result['total_assets'] == 0.0
        assert result['total_liabilities'] == 0.0
        assert result['total_equity'] == 0.0
        assert result['total_income'] == 0.0
        assert result['total_expenses'] == 0.0
        assert result['account_balances'] == []

    def test_get_timeseries_data_weekly_frequency(self, dashboard_service, accounts_with_data):
        """Test getting time-series data with weekly frequency."""
        start_date = (date.today() - timedelta(days=21)).isoformat()  # 3 weeks ago
        end_date = date.today().isoformat()
        
        result = dashboard_service.get_timeseries_data(
            start_date=start_date,
            end_date=end_date,
            frequency='weekly'
        )
        
        # Should have fewer data points than daily
        assert len(result['data_points']) <= 4  # Max 4 weeks
        assert len(result['data_points']) >= 1  # At least start date

    def test_get_timeseries_data_invalid_frequency(self, dashboard_service):
        """Test time-series data with invalid frequency."""
        start_date = date.today().isoformat()
        end_date = date.today().isoformat()
        
        with pytest.raises(ValidationError, match="Invalid frequency"):
            dashboard_service.get_timeseries_data(
                start_date=start_date,
                end_date=end_date,
                frequency='invalid'
            )

    def test_account_balance_calculations_asset_account(self, dashboard_service, db_session, transaction_service):
        """Test that asset account balances are calculated correctly."""
        # Create asset account
        asset_account = Account(name="Test Asset", type="ASSET", currency="USD")
        income_account = Account(name="Test Income", type="INCOME", currency="USD")
        db_session.add_all([asset_account, income_account])
        db_session.flush()
        
        # Create transaction: DR Asset, CR Income
        transaction_service.create_transaction(
            transaction_type='TRANSFER',
            date=date.today().isoformat(),
            memo='Test transaction',
            lines=[
                {'account_id': asset_account.id, 'dr_cr': 'DR', 'amount': Decimal('1000.00')},
                {'account_id': income_account.id, 'dr_cr': 'CR', 'amount': Decimal('1000.00')}
            ]
        )
        
        # Post transaction
        tx = db_session.query(Transaction).first()
        transaction_service.post_transaction(tx.id)
        
        result = dashboard_service.get_account_balances()
        
        # Asset should have positive balance of 1000
        asset_balance = next(acc for acc in result['account_balances'] if acc['account_id'] == asset_account.id)
        assert asset_balance['balance'] == 1000.0

    def test_account_balance_calculations_liability_account(self, dashboard_service, db_session, transaction_service):
        """Test that liability account balances are calculated correctly."""
        # Create liability account  
        liability_account = Account(name="Test Liability", type="LIABILITY", currency="USD")
        expense_account = Account(name="Test Expense", type="EXPENSE", currency="USD")
        db_session.add_all([liability_account, expense_account])
        db_session.flush()
        
        # Create transaction: DR Expense, CR Liability
        transaction_service.create_transaction(
            transaction_type='TRANSFER',
            date=date.today().isoformat(),
            memo='Test liability transaction',
            lines=[
                {'account_id': expense_account.id, 'dr_cr': 'DR', 'amount': Decimal('500.00')},
                {'account_id': liability_account.id, 'dr_cr': 'CR', 'amount': Decimal('500.00')}
            ]
        )
        
        # Post transaction
        tx = db_session.query(Transaction).first()
        transaction_service.post_transaction(tx.id)
        
        result = dashboard_service.get_account_balances()
        
        # Liability should have positive balance of 500
        liability_balance = next(acc for acc in result['account_balances'] if acc['account_id'] == liability_account.id)
        assert liability_balance['balance'] == 500.0