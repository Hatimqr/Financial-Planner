# Ledger TUI — Requirements Specification

A terminal-based personal finance tracker with double-entry accounting at its core.

---

## Overview

**Ledger TUI** is a fast, modern, keyboard-driven terminal application for managing personal finances. It follows the principles of double-entry bookkeeping, giving users the same rigor professional accountants use—but with the speed and simplicity of a CLI tool.

Think: Claude Code meets accounting.

---

## Design Philosophy

### Core Principles

1. **Local-First**: All data lives in a single SQLite file. No cloud, no accounts, no sync complexity.
2. **Clone-and-Run**: `git clone && make run`. That's it.
3. **Double-Entry by Default**: Every transaction touches two accounts. The books always balance.
4. **Keyboard-Driven**: Mouse optional. Vim-style navigation. Command palette for discoverability.
5. **Instant Startup**: Target <100ms cold start. No loading spinners.

### Aesthetic Goals

- Dense, information-rich displays (no wasted space)
- Minimal color palette—functional, not decorative
- Clear visual hierarchy through spacing and alignment
- Terminal-native feel (no "web app in a terminal" vibes)

---

## Architecture

### Tech Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.11+ | Rich ecosystem, Textual maturity |
| TUI Framework | Textual | Modern, async, CSS-like styling |
| Database | SQLite | Single file, zero config, SQL power |
| ORM | SQLAlchemy 2.0 | Type-safe, powerful query building |
| Migrations | Alembic | Schema versioning |

### Data Storage

store in repo directory for portability:

```
./
├── data/
│   └── ledger.db
├── pyproject.toml
└── src/
```

---

## Double-Entry Accounting Model

### The Fundamental Equation

```
Assets + Expenses = Liabilities + Equity + Income
```

Every transaction is a **journal entry** with two or more **line items** that must sum to zero (debits = credits).

### Account Types

| Type | Normal Balance | Examples |
|------|----------------|----------|
| **Asset** | Debit (+) | Bank accounts, investments, cash |
| **Liability** | Credit (+) | Credit cards, loans |
| **Equity** | Credit (+) | Opening balances, retained earnings |
| **Income** | Credit (+) | Salary, dividends, interest |
| **Expense** | Debit (+) | Food, rent, utilities |

### Account Hierarchy

Accounts are organized in a tree structure using `:` as delimiter:

```
Assets
├── Assets:Bank
│   ├── Assets:Bank:Chase:Checking
│   ├── Assets:Bank:Chase:Savings
│   └── Assets:Bank:Ally:HYSA
├── Assets:Investment
│   ├── Assets:Investment:Fidelity:401k
│   └── Assets:Investment:Vanguard:Brokerage
└── Assets:Cash

Liabilities
├── Liabilities:CreditCard
│   ├── Liabilities:CreditCard:Amex
│   └── Liabilities:CreditCard:Visa
└── Liabilities:Loan:Mortgage

Income
├── Income:Salary
├── Income:Bonus
├── Income:Dividends
└── Income:Interest

Expenses
├── Expenses:Food
│   ├── Expenses:Food:Groceries
│   ├── Expenses:Food:Restaurants
│   └── Expenses:Food:Coffee
├── Expenses:Housing
│   ├── Expenses:Housing:Rent
│   └── Expenses:Housing:Utilities
├── Expenses:Transport
└── Expenses:Entertainment

Equity
├── Equity:OpeningBalance
└── Equity:Adjustments
```

---

## Database Schema

### Core Tables

```sql
-- Account hierarchy
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,        -- Full path: "Assets:Bank:Chase:Checking"
    type TEXT NOT NULL,               -- asset, liability, equity, income, expense
    currency TEXT DEFAULT 'USD',
    is_placeholder BOOLEAN DEFAULT 0, -- Parent accounts that hold no transactions
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMP             -- Soft delete
);

-- Journal entries (the "header" of a transaction)
CREATE TABLE entries (
    id INTEGER PRIMARY KEY,
    date DATE NOT NULL,
    description TEXT NOT NULL,
    payee TEXT,
    status TEXT DEFAULT 'cleared',    -- pending, cleared, reconciled
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- Line items (the "splits" of a transaction)
CREATE TABLE postings (
    id INTEGER PRIMARY KEY,
    entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    amount DECIMAL(15,2) NOT NULL,    -- Positive = debit, Negative = credit
    memo TEXT,
    reconciled_at TIMESTAMP
);

-- Budget definitions
CREATE TABLE budgets (
    id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    period TEXT NOT NULL,             -- monthly, quarterly, yearly
    amount DECIMAL(15,2) NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE
);

-- Tags for flexible categorization
CREATE TABLE tags (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE entry_tags (
    entry_id INTEGER REFERENCES entries(id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (entry_id, tag_id)
);

-- Enforce double-entry: sum of postings must be zero
CREATE TRIGGER check_balance AFTER INSERT ON postings
BEGIN
    SELECT CASE
        WHEN (SELECT SUM(amount) FROM postings WHERE entry_id = NEW.entry_id) != 0
        THEN RAISE(ABORT, 'Transaction does not balance')
    END;
END;
```

---

## User Interface

### Screen Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│ LEDGER TUI                                    Net Worth: $45,230.00 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  [Dashboard]  Accounts  Transactions  Reports  Budgets              │
│                                                                     │
│  ┌─ This Month ──────────────────────────────────────────────────┐  │
│  │                                                               │  │
│  │   Income      $6,500.00   ████████████████████████████████░░  │  │
│  │   Expenses    $4,230.00   █████████████████████░░░░░░░░░░░░░  │  │
│  │   ───────────────────                                         │  │
│  │   Savings     $2,270.00   (34.9% rate)                        │  │
│  │                                                               │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─ Recent Transactions ─────────────────────────────────────────┐  │
│  │                                                               │  │
│  │  Dec 20  Whole Foods          Expenses:Food:Groceries  -89.34 │  │
│  │  Dec 19  Transfer             Assets:Bank:Savings     +500.00 │  │
│  │  Dec 18  Electric Company     Expenses:Housing:Utils   -67.50 │  │
│  │  Dec 17  Direct Deposit       Income:Salary         +3,250.00 │  │
│  │  Dec 15  Amazon               Expenses:Shopping        -42.99 │  │
│  │                                                               │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│ n: new  /: search  ?: help  q: quit                   Dec 20, 2024  │
└─────────────────────────────────────────────────────────────────────┘
```

### Views

#### 1. Dashboard
- Net worth summary (assets - liabilities)
- Income vs. expenses (current month, with comparison to previous)
- Savings rate
- Recent transactions (last 10)
- Budget status indicators

#### 2. Accounts
- Tree view of all accounts
- Running balance for each account
- Drill-down into account history
- Quick actions: reconcile, archive, edit

#### 3. Transactions (Ledger View)
- Sortable, filterable table of all entries
- Columns: Date, Description, Payee, Account(s), Amount, Status
- Inline editing
- Multi-select for bulk operations

#### 4. Reports
- Income Statement (P&L) for any period
- Balance Sheet (snapshot at a point in time)
- Cash Flow by category
- Spending trends (bar charts in terminal)
- Custom date range filtering

#### 5. Budgets
- Category budgets with progress bars
- Rollover support
- Historical comparison

---

## Keybindings

### Global

| Key | Action |
|-----|--------|
| `Ctrl+P` | Command palette |
| `g d` | Go to Dashboard |
| `g a` | Go to Accounts |
| `g t` | Go to Transactions |
| `g r` | Go to Reports |
| `g b` | Go to Budgets |
| `/` | Search |
| `?` | Help |
| `q` | Quit / Close modal |
| `Esc` | Cancel / Back |

### Navigation (Vim-style)

| Key | Action |
|-----|--------|
| `j` / `↓` | Move down |
| `k` / `↑` | Move up |
| `h` / `←` | Collapse / Left |
| `l` / `→` | Expand / Right |
| `g g` | Jump to top |
| `G` | Jump to bottom |
| `Ctrl+D` | Page down |
| `Ctrl+U` | Page up |

### Actions

| Key | Action |
|-----|--------|
| `n` | New transaction |
| `e` | Edit selected |
| `d d` | Delete selected |
| `y y` | Duplicate selected |
| `Enter` | Open / Select |
| `Space` | Toggle selection |
| `r` | Reconcile |
| `c` | Clear/unclear transaction |

---

## Features

### MVP (v0.1) — COMPLETED

- [x] Account management (create, edit, archive)
- [x] Transaction entry with double-entry validation
- [x] Basic account list view
- [x] Transaction list with filtering by account
- [x] Simple balance display
- [x] Data export (CSV, JSON)
- [x] SQLite database with schema migrations

### Core (v0.2) — COMPLETED

- [x] Dashboard with KPIs (net worth, income/expenses, savings rate)
- [x] Full keyboard navigation (Vim-style: j/k, gg/G, Ctrl+D/U)
- [x] Command palette (Ctrl+P with fuzzy search)
- [x] Date range filtering (This Month, Last Month, This Year)
- [x] Search across transactions
- [x] Category-based reports (Income Statement, Balance Sheet)
- [x] Budget tracking with progress bars

### Advanced (v0.3) — PLANNED

See [future-features.md](future-features.md) for detailed specifications.

- [ ] CSV import (bank statement parsing)
- [ ] Recurring transactions
- [ ] Transaction templates
- [ ] Multi-currency support
- [ ] Investment tracking (shares, cost basis)
- [ ] Reconciliation workflow
- [ ] Auto-backup on exit

### Power User (v1.0) — PLANNED

See [future-features.md](future-features.md) for detailed specifications.

- [ ] Rule-based auto-categorization
- [ ] Fuzzy matching for payees
- [ ] Split transactions (multi-line entries)
- [ ] Tags and custom fields
- [ ] CLI commands for scripting (`ledger add`, `ledger report`)
- [ ] Plain-text export (ledger-cli compatible)
- [ ] Encrypted database option

---

## Transaction Entry Flow

### Quick Add (Single-line)

Press `n` to open modal:

```
┌─ New Transaction ────────────────────────────────────────────────────┐
│                                                                      │
│  Date:        [2024-12-20]     (Tab to advance, Ctrl+D for picker)   │
│  Description: [Whole Foods groceries_________________]               │
│  Amount:      [$89.34_______]                                        │
│                                                                      │
│  From:        [Assets:Bank:Chase:Checking_____] ↓                    │
│  To:          [Expenses:Food:Groceries________] ↓                    │
│                                                                      │
│                                       [Cancel]  [Save]  [Save+New]   │
└──────────────────────────────────────────────────────────────────────┘
```

- Autocomplete on account fields
- Tab to navigate between fields
- Enter to save

### Full Entry (Multi-split)

For complex transactions (e.g., paycheck with taxes, 401k, etc.):

```
┌─ Journal Entry ──────────────────────────────────────────────────────┐
│                                                                      │
│  Date: 2024-12-17    Description: December Paycheck                  │
│                                                                      │
│  ┌─ Postings ────────────────────────────────────────────────────┐   │
│  │  Account                              Debit       Credit      │   │
│  │  ─────────────────────────────────────────────────────────────│   │
│  │  Assets:Bank:Chase:Checking          3,250.00                 │   │
│  │  Assets:Investment:401k                500.00                 │   │
│  │  Expenses:Tax:Federal                  750.00                 │   │
│  │  Expenses:Tax:State                    200.00                 │   │
│  │  Expenses:Tax:FICA                     300.00                 │   │
│  │  Income:Salary                                     5,000.00   │   │
│  │  ─────────────────────────────────────────────────────────────│   │
│  │  TOTAL                               5,000.00      5,000.00 ✓ │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                                                                      │
│                                       [Cancel]  [Save]               │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Reports

### Income Statement

```
┌─ Income Statement ───────────────────────────────────────────────────┐
│  Period: December 2024                                               │
│                                                                      │
│  INCOME                                                              │
│    Income:Salary                                          $6,500.00  │
│    Income:Dividends                                          $45.00  │
│    Income:Interest                                           $12.50  │
│  ──────────────────────────────────────────────────────────────────  │
│  Total Income                                             $6,557.50  │
│                                                                      │
│  EXPENSES                                                            │
│    Expenses:Housing:Rent                                  $1,800.00  │
│    Expenses:Food:Groceries                                  $450.00  │
│    Expenses:Food:Restaurants                                $180.00  │
│    Expenses:Transport                                       $250.00  │
│    Expenses:Utilities                                       $120.00  │
│    ...                                                               │
│  ──────────────────────────────────────────────────────────────────  │
│  Total Expenses                                           $4,230.00  │
│                                                                      │
│  ══════════════════════════════════════════════════════════════════  │
│  NET INCOME                                               $2,327.50  │
└──────────────────────────────────────────────────────────────────────┘
```

### Balance Sheet

```
┌─ Balance Sheet ──────────────────────────────────────────────────────┐
│  As of: December 20, 2024                                            │
│                                                                      │
│  ASSETS                                                              │
│    Assets:Bank:Chase:Checking                             $8,450.00  │
│    Assets:Bank:Chase:Savings                             $15,000.00  │
│    Assets:Bank:Ally:HYSA                                 $10,000.00  │
│    Assets:Investment:401k                                $45,000.00  │
│    Assets:Investment:Brokerage                           $12,000.00  │
│  ──────────────────────────────────────────────────────────────────  │
│  Total Assets                                            $90,450.00  │
│                                                                      │
│  LIABILITIES                                                         │
│    Liabilities:CreditCard:Amex                           ($1,200.00) │
│    Liabilities:CreditCard:Visa                             ($520.00) │
│  ──────────────────────────────────────────────────────────────────  │
│  Total Liabilities                                       ($1,720.00) │
│                                                                      │
│  ══════════════════════════════════════════════════════════════════  │
│  NET WORTH                                               $88,730.00  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Configuration

### config.toml

```toml
[general]
default_currency = "USD"
date_format = "%Y-%m-%d"
start_of_week = "monday"

[display]
theme = "dark"              # dark, light, auto
decimal_places = 2
thousands_separator = ","
negative_format = "parens"  # parens: ($100), minus: -$100

[keybindings]
# Override defaults
new_transaction = "n"
search = "/"

[accounts]
# Default accounts for quick entry
default_debit = "Assets:Bank:Chase:Checking"
default_credit = "Expenses:Uncategorized"

[backup]
auto_backup = true
backup_count = 10           # Keep last N backups
backup_on_exit = true

[import]
# Column mappings for CSV import
date_column = "Date"
description_column = "Description"
amount_column = "Amount"
```

---

## CLI Interface

For scripting and quick operations without launching the TUI:

```bash
# Launch TUI
ledger

# Quick transaction add
ledger add "Coffee" 5.50 --from checking --to food

# View account balance
ledger balance Assets:Bank:Chase:Checking

# Generate report
ledger report income --period 2024-12

# Export data
ledger export --format csv --output transactions.csv

# Import bank statement
ledger import statement.csv --account Assets:Bank:Chase:Checking

# Database operations
ledger db backup
ledger db vacuum
```

---

## Error Handling

### Validation Rules

1. **Balance Check**: Every entry must have postings that sum to zero
2. **Account Exists**: All referenced accounts must exist
3. **Date Sanity**: No future-dated transactions beyond +7 days
4. **Amount Precision**: Round to 2 decimal places for currencies

### User Feedback

- Inline validation errors (highlight field, show message)
- Non-blocking toasts for success messages
- Modal confirmations for destructive actions
- Undo support for last 10 operations

---

## Performance Targets

| Metric | Target |
|--------|--------|
| Cold start | <100ms |
| Transaction save | <50ms |
| Report generation (1 year) | <200ms |
| Search (10k transactions) | <100ms |
| Memory usage | <50MB |

---

## Future Considerations

- **Sync**: Optional encrypted sync via file (Dropbox/iCloud/Git)
- **Mobile companion**: Read-only web view for checking balances
- **Plugins**: Python-based extension system
- **AI assist**: Natural language transaction entry ("spent $50 at target yesterday")

---

## References

- [Textual Documentation](https://textual.textualize.io/)
- [Double-Entry Bookkeeping](https://en.wikipedia.org/wiki/Double-entry_bookkeeping)
- [Ledger CLI](https://www.ledger-cli.org/) — Inspiration for plain-text accounting
- [Beancount](https://beancount.github.io/) — Python-based plain-text accounting
- [hledger](https://hledger.org/) — Haskell-based ledger