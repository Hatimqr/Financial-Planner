"""Tests for account hierarchy features."""

import pytest

from ledger.services.account_service import AccountService


class TestAccountProperties:
    """Tests for Account model computed properties."""

    def test_account_depth(self, session, sample_accounts):
        """Test account depth calculation."""
        # Top-level account
        assert sample_accounts["assets"].depth == 0
        # Second level
        assert sample_accounts["assets_bank"].depth == 1
        # Third level
        assert sample_accounts["checking"].depth == 2

    def test_account_leaf_name(self, session, sample_accounts):
        """Test extracting leaf name from full path."""
        assert sample_accounts["assets"].leaf_name == "Assets"
        assert sample_accounts["assets_bank"].leaf_name == "Bank"
        assert sample_accounts["checking"].leaf_name == "Checking"

    def test_account_parent_name(self, session, sample_accounts):
        """Test getting parent account name."""
        assert sample_accounts["assets"].parent_name is None
        assert sample_accounts["assets_bank"].parent_name == "Assets"
        assert sample_accounts["checking"].parent_name == "Assets:Bank"

    def test_account_is_leaf(self, session, sample_accounts):
        """Test identifying leaf vs placeholder accounts."""
        # Placeholder accounts
        assert not sample_accounts["assets"].is_leaf
        assert not sample_accounts["food"].is_leaf
        # Leaf accounts
        assert sample_accounts["checking"].is_leaf
        assert sample_accounts["groceries"].is_leaf


class TestAccountRepository:
    """Tests for AccountRepository hierarchy methods."""

    def test_search_by_prefix(self, session, sample_accounts):
        """Test prefix search for autocomplete."""
        service = AccountService(session)

        # Search for assets
        results = service.search_accounts("Assets")
        result_names = [acc.name for acc in results]
        assert "Assets" in result_names
        assert "Assets:Bank" in result_names
        assert "Assets:Bank:Checking" in result_names

        # Search for specific path
        results = service.search_accounts("Assets:Bank")
        result_names = [acc.name for acc in results]
        assert "Assets:Bank" in result_names
        assert "Assets:Bank:Checking" in result_names
        # Should not include unrelated accounts
        assert "Expenses:Food" not in result_names

    def test_search_by_prefix_limit(self, session, sample_accounts):
        """Test prefix search respects limit."""
        service = AccountService(session)

        results = service.search_accounts("Expenses", limit=2)
        assert len(results) <= 2

    def test_get_leaf_accounts(self, session, sample_accounts):
        """Test getting only leaf (non-placeholder) accounts."""
        service = AccountService(session)

        leaf_accounts = service.get_leaf_accounts()
        for acc in leaf_accounts:
            assert acc.is_leaf
            assert not acc.is_placeholder

        # Verify placeholders are excluded
        leaf_names = [acc.name for acc in leaf_accounts]
        assert "Assets" not in leaf_names  # Placeholder
        assert "Expenses:Food" not in leaf_names  # Placeholder
        # Verify leaf accounts are included
        assert "Assets:Bank:Checking" in leaf_names
        assert "Expenses:Food:Groceries" in leaf_names

    def test_get_leaf_accounts_by_type(self, session, sample_accounts):
        """Test getting leaf accounts filtered by type."""
        service = AccountService(session)

        # Get only expense leaf accounts
        expense_leaves = service.get_leaf_accounts(account_type="expense")
        for acc in expense_leaves:
            assert acc.type == "expense"
            assert acc.is_leaf

        # Get only asset leaf accounts
        asset_leaves = service.get_leaf_accounts(account_type="asset")
        for acc in asset_leaves:
            assert acc.type == "asset"
            assert acc.is_leaf

    def test_get_root_accounts(self, session, sample_accounts):
        """Test getting top-level accounts."""
        service = AccountService(session)

        roots = service.get_root_accounts()
        root_names = [acc.name for acc in roots]

        # Should have top-level accounts
        assert "Assets" in root_names
        assert "Liabilities" in root_names
        assert "Expenses" in root_names
        assert "Income" in root_names
        assert "Equity" in root_names

        # Should not have children
        assert "Assets:Bank" not in root_names
        assert "Expenses:Food" not in root_names


class TestAccountHierarchyValidation:
    """Tests for account hierarchy type validation."""

    def test_create_account_with_matching_parent_type(self, session):
        """Test creating account with parent of same type succeeds."""
        service = AccountService(session)

        # Create parent
        service.create_account("Assets:Investments", "asset", is_placeholder=True)

        # Create child with matching type - should succeed
        child = service.create_account("Assets:Investments:Stocks", "asset")
        assert child.name == "Assets:Investments:Stocks"
        assert child.type == "asset"

    def test_create_account_with_mismatched_parent_type_fails(self, session, sample_accounts):
        """Test creating account with parent of different type fails."""
        service = AccountService(session)

        # Try to create expense account under Assets parent
        with pytest.raises(ValueError, match="doesn't match parent account type"):
            service.create_account("Assets:Bank:Groceries", "expense")

    def test_auto_create_parents_with_same_type(self, session):
        """Test that auto-created parents have same type as child."""
        service = AccountService(session)

        # Create deep account - parents should be auto-created with same type
        service.create_account("Expenses:Travel:Flights:International", "expense")

        # Check all parents were created with correct type
        travel = service.get_account_by_name("Expenses:Travel")
        assert travel is not None
        assert travel.type == "expense"
        assert travel.is_placeholder

        flights = service.get_account_by_name("Expenses:Travel:Flights")
        assert flights is not None
        assert flights.type == "expense"
        assert flights.is_placeholder


class TestAccountSuggestions:
    """Tests for smart account suggestions."""

    def test_suggest_grocery_expense(self, session, sample_accounts):
        """Test suggesting grocery account from description."""
        service = AccountService(session)

        suggestions = service.suggest_expense_account("Grocery shopping at Whole Foods")
        assert len(suggestions) > 0
        assert suggestions[0].name == "Expenses:Food:Groceries"

    def test_suggest_restaurant_expense(self, session, sample_accounts):
        """Test suggesting restaurant account from description."""
        service = AccountService(session)

        suggestions = service.suggest_expense_account("Dinner at Italian restaurant")
        assert len(suggestions) > 0
        assert suggestions[0].name == "Expenses:Food:Restaurants"

    def test_suggest_from_payee(self, session, sample_accounts):
        """Test suggesting account from payee name."""
        service = AccountService(session)

        suggestions = service.suggest_expense_account("Purchase", payee="Starbucks")
        assert len(suggestions) > 0
        assert suggestions[0].name == "Expenses:Food:Restaurants"

    def test_suggest_utilities_expense(self, session, sample_accounts):
        """Test suggesting utilities account."""
        service = AccountService(session)

        suggestions = service.suggest_expense_account("Electric bill payment")
        assert len(suggestions) > 0
        assert suggestions[0].name == "Expenses:Housing:Utilities"

    def test_suggest_transport_expense(self, session, sample_accounts):
        """Test suggesting transport account."""
        service = AccountService(session)

        suggestions = service.suggest_expense_account("Gas station fill-up")
        assert len(suggestions) > 0
        assert suggestions[0].name == "Expenses:Transport"

    def test_suggest_fallback_for_unknown(self, session, sample_accounts):
        """Test fallback to all expense accounts for unknown transactions."""
        service = AccountService(session)

        # Unknown description should return expense accounts
        suggestions = service.suggest_expense_account("Unknown transaction xyz123")
        assert len(suggestions) > 0
        # Should be expense accounts
        for acc in suggestions:
            assert acc.type == "expense"
            assert acc.is_leaf
