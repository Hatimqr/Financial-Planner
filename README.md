# Ledger TUI

A fast, keyboard-driven terminal app for managing personal finances with double-entry bookkeeping.

Your money, your machine, no cloud required.

---

## At a Glance

- **Double-entry accounting** — every transaction balances, just like a real ledger
- **5 screens** — Dashboard, Accounts, Transactions, Reports, Budgets
- **Vim-style navigation** — `j/k`, `gg/G`, `/` to search, `Ctrl+P` command palette
- **CSV import** — pull in bank statements with duplicate detection
- **CLI quick-add** — add transactions without opening the TUI
- **SQLite** — single file database, zero configuration
- **69 tests** — business logic thoroughly covered

---

## Quick Start

```bash
# Clone and set up
git clone <repository-url>
cd financial-planning
pip install -e ".[dev]"

# Initialize the database
alembic upgrade head

# (Optional) Load sample data to explore
python -m ledger seed

# Launch
python -m ledger run
```

---

## Screens

### Dashboard (`d`)

Your financial snapshot at a glance:
- **Net worth** — total assets minus liabilities
- **Income & expenses** — this month's numbers with savings rate
- **Recent transactions** — last 10 entries
- **Expense breakdown** — top spending categories

### Accounts (`a`)

Hierarchical view of all your accounts with live balances. Accounts are organized in a tree using `:` delimiters:

```
Assets
  Bank
    Checking          $5,230.00
    Savings          $12,000.00
Expenses
  Food
    Groceries          $450.00
    Restaurants        $180.00
```

### Transactions (`t`)

Full transaction list with:
- **Date filters** — All, This Month, Last Month, This Year
- **Search** — find transactions by description
- **Detail view** — press `Enter` to see all postings
- **Edit** — press `e` to modify any transaction
- **Delete** — press `Delete` with confirmation dialog

### Reports (`r`)

Two financial reports with configurable time periods:

- **Income Statement** — income vs. expenses with net income
- **Balance Sheet** — assets, liabilities, and net worth

### Budgets (`b`)

Visual budget tracking with progress bars. Set monthly, quarterly, or yearly budgets per expense category and see how you're tracking.

---

## Keyboard Shortcuts

### Navigation

| Key | Action |
|-----|--------|
| `d` | Dashboard |
| `a` | Accounts |
| `t` | Transactions |
| `r` | Reports |
| `b` | Budgets |
| `Ctrl+P` | Command palette (fuzzy search) |
| `?` | Help overlay |
| `q` | Quit |

### Vim-Style Movement

| Key | Action |
|-----|--------|
| `j` / `k` | Down / Up |
| `gg` / `G` | Top / Bottom |
| `Ctrl+D` / `Ctrl+U` | Page down / Page up |

### Transaction Actions

| Key | Action |
|-----|--------|
| `n` | New transaction |
| `Enter` | View transaction details |
| `e` | Edit selected transaction |
| `Delete` | Delete (with confirmation) |
| `/` | Search transactions |

---

## CLI Commands

You don't have to open the TUI for everything. Common operations work directly from the terminal.

### Quick-Add a Transaction

```bash
# Basic: description, amount, from account, to account
ledger add "Coffee" 5.50 --from checking --to food

# With date and payee
ledger add "Groceries" 85.20 -f checking -t groceries -d 2025-01-15 -p "Whole Foods"

# Income
ledger add "Salary" 3000 --from salary --to checking
```

Account names are fuzzy-matched — `checking` matches `Assets:Bank:Checking`.

### Import Bank Statements

```bash
# Import a CSV file
ledger import statement.csv --from checking --to groceries

# Use a bank-specific format
ledger import chase_statement.csv -f checking -t groceries --format chase

# Supported formats: generic, chase, bofa
```

The import process:
1. Parses the CSV according to the format preset
2. Detects duplicates (same date + amount + description)
3. Shows a preview of what will be imported
4. Imports valid, non-duplicate transactions

### Export Data

```bash
# Export transactions to CSV
ledger export csv -o transactions.csv

# Export accounts to JSON
ledger export json -o accounts.json -t accounts
```

### Other Commands

```bash
ledger run        # Launch the TUI
ledger init       # Initialize database with sample accounts
ledger seed       # Add sample transactions
```

---

## CSV Import (TUI)

You can also import CSVs from within the TUI using the command palette (`Ctrl+P` then type "Import"):

1. Enter the CSV file path
2. Select the bank format preset (Generic, Chase, Bank of America)
3. Choose your source account (e.g., your checking account)
4. Choose a default target account for uncategorized transactions
5. Click "Preview" to see what will be imported
6. Review the preview — duplicates and errors are flagged
7. Click "Import" to commit

---

## How Double-Entry Works

Every transaction has two sides that balance to zero:

```
Buying groceries for $50:
  Assets:Bank:Checking     -$50.00  (money leaves your bank)
  Expenses:Food:Groceries  +$50.00  (expense is recorded)
                           --------
  Net:                       $0.00  (always balanced)

Receiving salary of $3,000:
  Income:Salary            -$3,000  (income source)
  Assets:Bank:Checking     +$3,000  (money arrives)
                           --------
  Net:                       $0.00
```

This means your books always balance. The system enforces this — you can't save an unbalanced transaction.

### Account Types

| Type | What It Tracks | Examples |
|------|---------------|----------|
| **Asset** | Things you own | Bank accounts, cash, investments |
| **Liability** | Things you owe | Credit cards, loans |
| **Income** | Money coming in | Salary, dividends, interest |
| **Expense** | Money going out | Food, rent, utilities |
| **Equity** | Net worth adjustments | Opening balances |

### Account Hierarchy

Accounts are organized in a tree using `:` as a separator:

```
Assets:Bank:Chase:Checking
Expenses:Food:Groceries
Income:Salary
```

Parent accounts (like `Assets:Bank`) are automatically created as placeholders when you create child accounts.

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| TUI | [Textual](https://textual.textualize.io/) |
| Database | SQLite (WAL mode) |
| ORM | SQLAlchemy 2.0 |
| Migrations | Alembic |
| CLI | Click |
| Testing | pytest (69 tests) |

---

## Development

### Prerequisites

- Python 3.11 or higher
- pip (or conda for environment management)

### Setup

```bash
# With conda (recommended)
conda create -n fin_man python=3.11
conda activate fin_man
pip install -e ".[dev]"
alembic upgrade head

# Run tests
pytest tests/ -v

# Lint
ruff check src/ledger
```

### Project Structure

```
src/ledger/
├── cli/           # CLI commands
├── db/            # Models, migrations, connection
├── repositories/  # Data access layer
├── services/      # Business logic (6 services)
└── tui/           # Terminal UI (5 screens, 8 widgets)
```

Architecture: `TUI/CLI -> Services -> Repositories -> Database`

See [docs/architecture.md](docs/architecture.md) for details.

---

## Roadmap

See [docs/future-features.md](docs/future-features.md) for the full list.

**Coming next:**
- Recurring transactions (auto-generate rent, salary, subscriptions)
- Auto-categorization (rules to categorize imports automatically)
- Transaction templates (save common entries for reuse)

---

## References

- [Textual Documentation](https://textual.textualize.io/)
- [Double-Entry Bookkeeping](https://en.wikipedia.org/wiki/Double-entry_bookkeeping)
- [Ledger CLI](https://www.ledger-cli.org/) — Inspiration
- [Beancount](https://beancount.github.io/) — Python plain-text accounting
