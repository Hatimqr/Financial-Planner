"""
Integration tests for dashboard API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import date, timedelta
from decimal import Decimal

from main import app
from app.services.transaction_service import TransactionService
from app.models import Account, Transaction
from app.db import get_db


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def override_db_dependency(db_session):
    """Override the database dependency for testing."""
    def _get_test_db():
        return db_session
    
    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def test_accounts_with_transactions(db_session, override_db_dependency):
    """Create test accounts with sample transactions."""
    # Create accounts
    checking = Account(name="Checking Account", type="ASSET", currency="USD")
    savings = Account(name="Savings Account", type="ASSET", currency="USD") 
    credit_card = Account(name="Credit Card", type="LIABILITY", currency="USD")
    salary = Account(name="Salary", type="INCOME", currency="USD")
    groceries = Account(name="Groceries", type="EXPENSE", currency="USD")
    
    db_session.add_all([checking, savings, credit_card, salary, groceries])
    db_session.flush()
    
    # Create transactions using transaction service
    tx_service = TransactionService(db_session)
    
    today = date.today()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    
    # Salary deposit (week ago)
    tx1 = tx_service.create_transaction(
        transaction_type='TRANSFER',
        date=week_ago.isoformat(),
        memo='Salary deposit',
        lines=[
            {'account_id': checking.id, 'dr_cr': 'DR', 'amount': Decimal('5000.00')},
            {'account_id': salary.id, 'dr_cr': 'CR', 'amount': Decimal('5000.00')}
        ]
    )
    tx_service.post_transaction(tx1.id)
    
    # Transfer to savings (yesterday)
    tx2 = tx_service.create_transaction(
        transaction_type='TRANSFER',
        date=yesterday.isoformat(),
        memo='Transfer to savings',
        lines=[
            {'account_id': checking.id, 'dr_cr': 'CR', 'amount': Decimal('2000.00')},
            {'account_id': savings.id, 'dr_cr': 'DR', 'amount': Decimal('2000.00')}
        ]
    )
    tx_service.post_transaction(tx2.id)
    
    # Credit card purchase (today)
    tx3 = tx_service.create_transaction(
        transaction_type='TRANSFER',
        date=today.isoformat(),
        memo='Grocery shopping',
        lines=[
            {'account_id': groceries.id, 'dr_cr': 'DR', 'amount': Decimal('150.00')},
            {'account_id': credit_card.id, 'dr_cr': 'CR', 'amount': Decimal('150.00')}
        ]
    )
    tx_service.post_transaction(tx3.id)
    
    return {
        'checking': checking,
        'savings': savings,
        'credit_card': credit_card,
        'salary': salary,
        'groceries': groceries
    }


class TestDashboardSummaryEndpoint:
    """Test the /api/dashboard/summary endpoint."""

    def test_get_dashboard_summary_success(self, client, test_accounts_with_transactions):
        """Test successful dashboard summary retrieval."""
        response = client.get("/api/dashboard/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "net_worth" in data
        assert "total_assets" in data
        assert "total_liabilities" in data
        assert "total_equity" in data
        assert "total_income" in data
        assert "total_expenses" in data
        assert "account_balances" in data
        
        # Check calculations
        # Assets: Checking (3000) + Savings (2000) = 5000
        # Liabilities: Credit Card (150) = 150
        # Net worth: 5000 - 150 = 4850
        assert data["net_worth"] == 4850.0
        assert data["total_assets"] == 5000.0
        assert data["total_liabilities"] == 150.0
        assert data["total_income"] == 5000.0
        assert data["total_expenses"] == 150.0
        
        # Check account balances
        assert len(data["account_balances"]) == 5
        
        # Find specific account balances
        account_balances = {acc["account_name"]: acc["balance"] for acc in data["account_balances"]}
        assert account_balances["Checking Account"] == 3000.0
        assert account_balances["Savings Account"] == 2000.0
        assert account_balances["Credit Card"] == 150.0

    def test_get_dashboard_summary_with_account_filter(self, client, test_accounts_with_transactions):
        """Test dashboard summary with account ID filtering."""
        checking_id = test_accounts_with_transactions['checking'].id
        savings_id = test_accounts_with_transactions['savings'].id
        
        response = client.get(f"/api/dashboard/summary?account_ids={checking_id}&account_ids={savings_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should only include checking and savings accounts
        assert len(data["account_balances"]) == 2
        account_names = {acc["account_name"] for acc in data["account_balances"]}
        assert account_names == {"Checking Account", "Savings Account"}
        
        # Net worth should only consider these accounts (no liabilities included)
        assert data["net_worth"] == 5000.0
        assert data["total_assets"] == 5000.0
        assert data["total_liabilities"] == 0.0

    def test_get_dashboard_summary_with_date_filter(self, client, test_accounts_with_transactions):
        """Test dashboard summary with as_of_date filtering."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        
        response = client.get(f"/api/dashboard/summary?as_of_date={yesterday}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should not include today's credit card transaction
        account_balances = {acc["account_name"]: acc["balance"] for acc in data["account_balances"]}
        assert account_balances.get("Credit Card", 0.0) == 0.0
        assert account_balances.get("Groceries", 0.0) == 0.0

    def test_get_dashboard_summary_invalid_date(self, client):
        """Test dashboard summary with invalid date format."""
        response = client.get("/api/dashboard/summary?as_of_date=invalid-date")
        
        assert response.status_code == 400
        response_data = response.json()
        # Check custom error format
        assert response_data["ok"] is False
        assert "Invalid date format" in response_data["error"]["message"]

    def test_get_dashboard_summary_empty_database(self, client, override_db_dependency):
        """Test dashboard summary with empty database."""
        response = client.get("/api/dashboard/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["net_worth"] == 0.0
        assert data["total_assets"] == 0.0
        assert data["total_liabilities"] == 0.0
        assert data["account_balances"] == []


class TestDashboardTimeseriesEndpoint:
    """Test the /api/dashboard/timeseries endpoint."""

    def test_get_timeseries_success(self, client, test_accounts_with_transactions):
        """Test successful timeseries data retrieval."""
        start_date = (date.today() - timedelta(days=7)).isoformat()
        end_date = date.today().isoformat()
        
        response = client.get(f"/api/dashboard/timeseries?start_date={start_date}&end_date={end_date}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "data_points" in data
        assert "account_info" in data
        
        # Check that we have data points
        assert len(data["data_points"]) >= 1
        
        # Check data point structure
        data_point = data["data_points"][0]
        assert "date" in data_point
        assert "accounts" in data_point
        assert "net_worth" in data_point
        
        # Check account info structure
        assert len(data["account_info"]) == 5  # All accounts
        for account_id, info in data["account_info"].items():
            assert "name" in info
            assert "type" in info

    def test_get_timeseries_with_account_filter(self, client, test_accounts_with_transactions):
        """Test timeseries with account filtering."""
        checking_id = test_accounts_with_transactions['checking'].id
        start_date = (date.today() - timedelta(days=7)).isoformat()
        end_date = date.today().isoformat()
        
        response = client.get(
            f"/api/dashboard/timeseries?start_date={start_date}&end_date={end_date}&account_ids={checking_id}"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should only include checking account
        assert len(data["account_info"]) == 1
        assert str(checking_id) in data["account_info"]

    def test_get_timeseries_weekly_frequency(self, client, test_accounts_with_transactions):
        """Test timeseries with weekly frequency."""
        start_date = (date.today() - timedelta(days=21)).isoformat()
        end_date = date.today().isoformat()
        
        response = client.get(
            f"/api/dashboard/timeseries?start_date={start_date}&end_date={end_date}&frequency=weekly"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have fewer data points than daily
        assert len(data["data_points"]) <= 4

    def test_get_timeseries_missing_required_params(self, client):
        """Test timeseries endpoint with missing required parameters."""
        response = client.get("/api/dashboard/timeseries")
        
        assert response.status_code == 422  # Validation error

    def test_get_timeseries_invalid_frequency(self, client):
        """Test timeseries with invalid frequency."""
        start_date = date.today().isoformat()
        end_date = date.today().isoformat()
        
        response = client.get(
            f"/api/dashboard/timeseries?start_date={start_date}&end_date={end_date}&frequency=invalid"
        )
        
        assert response.status_code == 400
        response_data = response.json()
        assert response_data["ok"] is False
        assert "Frequency must be" in response_data["error"]["message"]

    def test_get_timeseries_invalid_date_format(self, client):
        """Test timeseries with invalid date format."""
        response = client.get("/api/dashboard/timeseries?start_date=invalid&end_date=2024-01-01")
        
        assert response.status_code == 400


class TestAccountLedgerEndpoint:
    """Test the /api/dashboard/accounts/{account_id}/ledger endpoint."""

    def test_get_account_ledger_success(self, client, test_accounts_with_transactions):
        """Test successful account ledger retrieval."""
        checking_id = test_accounts_with_transactions['checking'].id
        
        response = client.get(f"/api/dashboard/accounts/{checking_id}/ledger")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "account" in data
        assert "ledger_entries" in data
        assert "total_entries" in data
        assert "has_more" in data
        
        # Check account info
        account_info = data["account"]
        assert account_info["id"] == checking_id
        assert account_info["name"] == "Checking Account"
        assert account_info["type"] == "ASSET"
        assert account_info["current_balance"] == 3000.0
        
        # Check ledger entries
        assert len(data["ledger_entries"]) == 2  # Salary + transfer
        assert data["total_entries"] == 2
        assert data["has_more"] is False
        
        # Check entry structure
        entry = data["ledger_entries"][0]
        assert "transaction_id" in entry
        assert "transaction_line_id" in entry
        assert "date" in entry
        assert "memo" in entry
        assert "transaction_type" in entry
        assert "side" in entry
        assert "amount" in entry
        assert "running_balance" in entry

    def test_get_account_ledger_with_date_filter(self, client, test_accounts_with_transactions):
        """Test account ledger with date filtering."""
        checking_id = test_accounts_with_transactions['checking'].id
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        
        response = client.get(f"/api/dashboard/accounts/{checking_id}/ledger?start_date={yesterday}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should only include transfer transaction from yesterday
        assert len(data["ledger_entries"]) == 1
        assert data["ledger_entries"][0]["memo"] == "Transfer to savings"

    def test_get_account_ledger_with_pagination(self, client, test_accounts_with_transactions):
        """Test account ledger with pagination."""
        checking_id = test_accounts_with_transactions['checking'].id
        
        # Get first page
        response = client.get(f"/api/dashboard/accounts/{checking_id}/ledger?limit=1&offset=0")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["ledger_entries"]) == 1
        assert data["total_entries"] == 2
        assert data["has_more"] is True
        
        # Get second page
        response2 = client.get(f"/api/dashboard/accounts/{checking_id}/ledger?limit=1&offset=1")
        
        assert response2.status_code == 200
        data2 = response2.json()
        
        assert len(data2["ledger_entries"]) == 1
        assert data2["total_entries"] == 2
        assert data2["has_more"] is False

    def test_get_account_ledger_nonexistent_account(self, client, override_db_dependency):
        """Test account ledger for non-existent account."""
        response = client.get("/api/dashboard/accounts/99999/ledger")
        
        assert response.status_code == 404

    def test_get_account_ledger_invalid_date_format(self, client, test_accounts_with_transactions):
        """Test account ledger with invalid date format."""
        checking_id = test_accounts_with_transactions['checking'].id
        
        response = client.get(f"/api/dashboard/accounts/{checking_id}/ledger?start_date=invalid-date")
        
        assert response.status_code == 400
        response_data = response.json()
        assert response_data["ok"] is False
        assert "Invalid start_date format" in response_data["error"]["message"]

    def test_get_account_ledger_pagination_limits(self, client, test_accounts_with_transactions):
        """Test account ledger pagination parameter validation."""
        checking_id = test_accounts_with_transactions['checking'].id
        
        # Test limit too high
        response = client.get(f"/api/dashboard/accounts/{checking_id}/ledger?limit=2000")
        assert response.status_code == 422  # Validation error
        
        # Test limit too low
        response = client.get(f"/api/dashboard/accounts/{checking_id}/ledger?limit=0")
        assert response.status_code == 422  # Validation error
        
        # Test negative offset
        response = client.get(f"/api/dashboard/accounts/{checking_id}/ledger?offset=-1")
        assert response.status_code == 422  # Validation error


class TestDashboardEndpointsWithNoData:
    """Test dashboard endpoints with empty or minimal data."""

    def test_all_endpoints_with_empty_database(self, client, override_db_dependency):
        """Test that all dashboard endpoints handle empty database gracefully."""
        # Test summary endpoint
        response = client.get("/api/dashboard/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["net_worth"] == 0.0
        assert data["account_balances"] == []
        
        # Test timeseries endpoint
        start_date = date.today().isoformat()
        end_date = date.today().isoformat()
        response = client.get(f"/api/dashboard/timeseries?start_date={start_date}&end_date={end_date}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["data_points"]) >= 1  # Should have at least one data point
        assert data["account_info"] == {}

    def test_accounts_with_no_transactions(self, client, db_session, override_db_dependency):
        """Test dashboard with accounts but no transactions."""
        # Create accounts without transactions
        checking = Account(name="Empty Checking", type="ASSET", currency="USD")
        db_session.add(checking)
        db_session.flush()
        
        # Test summary
        response = client.get("/api/dashboard/summary")
        assert response.status_code == 200
        data = response.json()
        
        # Should have account with zero balance
        assert len(data["account_balances"]) == 1
        assert data["account_balances"][0]["balance"] == 0.0
        
        # Test ledger
        response = client.get(f"/api/dashboard/accounts/{checking.id}/ledger")
        assert response.status_code == 200
        data = response.json()
        
        assert data["account"]["current_balance"] == 0.0
        assert len(data["ledger_entries"]) == 0
        assert data["total_entries"] == 0