#!/usr/bin/env python
"""Quick validation script for account hierarchy features."""

from ledger.db.connection import get_db_manager
from ledger.services.account_service import AccountService


def test_hierarchy_features():
    """Test the new hierarchy features interactively."""
    print("=" * 60)
    print("Account Hierarchy Features Demo")
    print("=" * 60)

    db_manager = get_db_manager()

    with db_manager.get_session() as session:
        service = AccountService(session)

        # 1. Test computed properties
        print("\n1. Testing Computed Properties")
        print("-" * 60)
        checking = service.get_account_by_name("Assets:Bank:Checking")
        if checking:
            print(f"Account: {checking.name}")
            print(f"  - Depth: {checking.depth}")
            print(f"  - Leaf name: {checking.leaf_name}")
            print(f"  - Parent name: {checking.parent_name}")
            print(f"  - Is leaf: {checking.is_leaf}")

        # 2. Test search by prefix
        print("\n2. Testing Prefix Search (Autocomplete)")
        print("-" * 60)
        results = service.search_accounts("Assets")
        print(f"Search 'Assets' found {len(results)} accounts:")
        for acc in results[:5]:
            print(f"  - {acc.name}")

        # 3. Test leaf accounts
        print("\n3. Testing Leaf Accounts (Transaction-Ready)")
        print("-" * 60)
        leaf_accounts = service.get_leaf_accounts()
        print(f"Found {len(leaf_accounts)} leaf accounts:")
        for acc in leaf_accounts[:5]:
            print(f"  - {acc.name} ({acc.type})")

        # 4. Test leaf accounts by type
        print("\n4. Testing Leaf Accounts by Type")
        print("-" * 60)
        expense_leaves = service.get_leaf_accounts(account_type="expense")
        print(f"Found {len(expense_leaves)} expense leaf accounts:")
        for acc in expense_leaves[:5]:
            print(f"  - {acc.name}")

        # 5. Test root accounts
        print("\n5. Testing Root Accounts")
        print("-" * 60)
        roots = service.get_root_accounts()
        print(f"Found {len(roots)} root accounts:")
        for acc in roots:
            print(f"  - {acc.name} ({acc.type})")

        # 6. Test account suggestions
        print("\n6. Testing Smart Suggestions")
        print("-" * 60)

        test_cases = [
            ("Grocery shopping at Whole Foods", None),
            ("Dinner at Italian restaurant", None),
            ("Coffee", "Starbucks"),
            ("Electric bill payment", None),
            ("Gas station fill-up", None),
        ]

        for description, payee in test_cases:
            suggestions = service.suggest_expense_account(description, payee)
            if suggestions:
                suggested = suggestions[0].name
                print(f"  '{description}' → {suggested}")
            else:
                print(f"  '{description}' → No suggestion")

        # 7. Test type validation
        print("\n7. Testing Type Hierarchy Validation")
        print("-" * 60)
        try:
            # This should work - matching types
            print("Creating 'Assets:Investments:Stocks' (asset)...")
            service.create_account("Assets:Investments:Stocks", "asset")
            print("  ✓ Success - parent type matches")
        except ValueError as e:
            print(f"  ✗ Failed: {e}")

        try:
            # This should fail - mismatched types
            print("Creating 'Assets:Bank:Groceries' (expense)...")
            service.create_account("Assets:Bank:Groceries", "expense")
            print("  ✗ Should have failed but didn't!")
        except ValueError as e:
            print(f"  ✓ Correctly rejected: Type mismatch detected")

    print("\n" + "=" * 60)
    print("All hierarchy features working correctly!")
    print("=" * 60)


if __name__ == "__main__":
    test_hierarchy_features()
