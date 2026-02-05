# Account Hierarchy System

## Overview

The Ledger TUI uses a hierarchical account structure based on colon-separated paths (`:`) similar to a filesystem. This document describes how the hierarchy works and the features available for managing accounts.

## Account Structure

### Path Format

Accounts use colon-delimited paths to represent parent-child relationships:

```
Assets                        (top-level, placeholder)
├── Assets:Bank               (parent, placeholder)
│   ├── Assets:Bank:Checking  (leaf account)
│   └── Assets:Bank:Savings   (leaf account)
└── Assets:Cash               (leaf account)
```

### Account Types

Every account must be one of five types, and **all accounts in a hierarchy branch must share the same type**:

1. **asset** - Things you own (bank accounts, cash, investments)
2. **liability** - Things you owe (credit cards, loans, mortgages)
3. **equity** - Opening balances, retained earnings, adjustments
4. **income** - Money coming in (salary, interest, dividends)
5. **expense** - Money going out (rent, food, utilities, entertainment)

### Placeholder Accounts

- **Placeholder accounts** (`is_placeholder=True`) are organizational containers
- They cannot have transactions posted directly to them
- They exist to organize child accounts into categories
- Auto-created when you create a deep account path

**Example:**
```python
# Creating this account...
service.create_account("Expenses:Travel:Flights:International", "expense")

# ...automatically creates these placeholders:
# - Expenses (placeholder)
# - Expenses:Travel (placeholder)
# - Expenses:Travel:Flights (placeholder)
# - Expenses:Travel:Flights:International (leaf, can have transactions)
```

## Account Properties

### Computed Properties

Every account has these convenient properties:

```python
account = service.get_account_by_name("Assets:Bank:Checking")

account.depth        # 2 (number of colons)
account.leaf_name    # "Checking" (just the account name)
account.parent_name  # "Assets:Bank" (parent path)
account.is_leaf      # True (not a placeholder)
```

## Hierarchy Operations

### 1. Search & Autocomplete

Find accounts by prefix for autocomplete:

```python
# Search for all accounts starting with "Assets"
accounts = service.search_accounts("Assets", limit=10)
# Returns: Assets, Assets:Bank, Assets:Bank:Checking, Assets:Bank:Savings, Assets:Cash
```

### 2. Get Leaf Accounts

Get only accounts that can have transactions (non-placeholders):

```python
# All leaf accounts
leaf_accounts = service.get_leaf_accounts()

# Leaf accounts of specific type
expense_accounts = service.get_leaf_accounts(account_type="expense")
```

This is used in the transaction form to show only valid accounts for posting.

### 3. Get Root Accounts

Get top-level accounts:

```python
roots = service.get_root_accounts()
# Returns: Assets, Liabilities, Equity, Income, Expenses
```

### 4. Account Hierarchy Tree

Get all accounts in hierarchical order:

```python
tree = service.get_account_hierarchy_tree()
# Returns accounts sorted by name, creating natural tree structure
```

## Smart Categorization

### Auto-Suggest Expense Accounts

The system can suggest expense accounts based on transaction descriptions and payee names:

```python
# Suggest account for grocery shopping
suggestions = service.suggest_expense_account(
    description="Grocery shopping",
    payee="Whole Foods"
)
# Returns: [Expenses:Food:Groceries]

# Suggest account for dining out
suggestions = service.suggest_expense_account(
    description="Dinner out",
    payee="Italian Restaurant"
)
# Returns: [Expenses:Food:Restaurants]
```

### Keyword Mappings

The system recognizes these common keywords:

**Food & Dining:**
- grocery, groceries, supermarket → `Expenses:Food:Groceries`
- restaurant, dining, dinner, lunch, cafe, coffee → `Expenses:Food:Restaurants`

**Housing:**
- rent → `Expenses:Housing:Rent`
- electric, electricity, power, water, gas bill, internet, utilities → `Expenses:Housing:Utilities`

**Transportation:**
- gas, fuel, shell, chevron, uber, lyft → `Expenses:Transport`

**Entertainment:**
- movie, cinema, theater, concert → `Expenses:Entertainment`

## Validation Rules

### Type Consistency

Parent and child accounts **must have the same type**:

```python
# ✅ Valid - parent and child are both assets
service.create_account("Assets:Bank:Chase:Checking", "asset")

# ❌ Invalid - mixing types in hierarchy
service.create_account("Assets:Bank:Groceries", "expense")
# Raises: ValueError: Account type 'expense' doesn't match parent account type 'asset'
```

### Unique Names

Account names must be unique across the entire chart of accounts:

```python
# ✅ First creation succeeds
service.create_account("Assets:Bank:Checking", "asset")

# ❌ Duplicate fails
service.create_account("Assets:Bank:Checking", "asset")
# Raises: ValueError: Account 'Assets:Bank:Checking' already exists
```

### Auto-Created Parents

When creating a deep account, missing parents are automatically created as placeholders:

```python
# Creates entire hierarchy automatically
service.create_account("Expenses:Travel:Flights:International", "expense")

# Now these all exist:
# - Expenses (placeholder, auto-created)
# - Expenses:Travel (placeholder, auto-created)
# - Expenses:Travel:Flights (placeholder, auto-created)
# - Expenses:Travel:Flights:International (leaf account)
```

## Usage Examples

### Creating Accounts

```python
from ledger.services.account_service import AccountService

service = AccountService(session)

# Create a simple account
checking = service.create_account("Assets:Bank:Checking", "asset")

# Create with optional parameters
savings = service.create_account(
    name="Assets:Bank:Savings",
    account_type="asset",
    currency="USD",
    notes="High-yield savings account"
)

# Create placeholder explicitly
service.create_account(
    name="Expenses:Travel",
    account_type="expense",
    is_placeholder=True
)
```

### Finding Accounts

```python
# By exact name
account = service.get_account_by_name("Assets:Bank:Checking")

# By prefix (autocomplete)
results = service.search_accounts("Assets:Bank")

# By type
all_expenses = service.get_accounts_by_type("expense")

# Only leaf accounts (for transactions)
postable_accounts = service.get_leaf_accounts()

# Only expense leaf accounts
expense_leaves = service.get_leaf_accounts(account_type="expense")
```

### Account Suggestions

```python
# Get suggestion based on description
suggestions = service.suggest_expense_account(
    description="Coffee at Starbucks",
    payee="Starbucks"
)
# Returns: [Expenses:Food:Restaurants]

# Use first suggestion or let user choose
if suggestions:
    suggested_account = suggestions[0]
else:
    # Fallback to showing all expense accounts
    pass
```

## Best Practices

### 1. Use Meaningful Hierarchies

Organize accounts in a way that makes sense for reporting:

```
Expenses
├── Food
│   ├── Groceries
│   └── Restaurants
├── Housing
│   ├── Rent
│   └── Utilities
└── Transport
```

### 2. Keep Depth Reasonable

3-4 levels is usually sufficient. Deeper hierarchies become harder to manage:

```
✅ Good:  Expenses:Food:Groceries
✅ Good:  Expenses:Travel:Flights:International
❌ Too deep: Expenses:Food:Dining:Restaurants:Italian:Fine:Michelin
```

### 3. Use Placeholders for Grouping

Mark organizational accounts as placeholders:

```python
# Create category placeholders
service.create_account("Expenses:Food", "expense", is_placeholder=True)

# Then create leaf accounts under them
service.create_account("Expenses:Food:Groceries", "expense")
service.create_account("Expenses:Food:Restaurants", "expense")
```

### 4. Transaction Forms Show Only Leaf Accounts

The TUI automatically filters to show only non-placeholder accounts in transaction forms, preventing users from posting to organizational categories.

## Testing

Comprehensive tests ensure hierarchy features work correctly:

```bash
# Run hierarchy tests
pytest tests/unit/test_account_hierarchy.py -v
```

Tests cover:
- Computed properties (depth, leaf_name, parent_name, is_leaf)
- Search and filtering (prefix search, leaf accounts, root accounts)
- Type validation (matching parent types, auto-created parents)
- Smart suggestions (keyword matching, fallback behavior)
