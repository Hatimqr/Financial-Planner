# Ledger TUI

A fast, modern, keyboard-driven terminal application for managing personal finances using double-entry bookkeeping.

**Think: Claude Code meets accounting.**

## Features

### Core Features (v0.2)

- **Double-Entry Accounting**: Every transaction touches two accounts. The books always balance.
- **Local-First**: All data lives in a single SQLite file. No cloud, no accounts, no sync complexity.
- **Keyboard-Driven**: Mouse optional. Vim-style navigation. Command palette for discoverability.
- **Instant Startup**: Target <100ms cold start.
- **Terminal-Native**: Dense, information-rich displays with minimal color.

### Screens

| Screen       | Key   | Description                                                             |
| ------------ | ----- | ----------------------------------------------------------------------- |
| Dashboard    | `d` | Net worth, income/expenses KPIs, recent transactions, expense breakdown |
| Accounts     | `a` | Hierarchical account tree with balances                                 |
| Transactions | `t` | Transaction list with date filtering and search                         |
| Reports      | `r` | Income Statement and Balance Sheet                                      |
| Budgets      | `b` | Budget tracking with visual progress bars                               |

### Keyboard Navigation

**Global:**

- `Ctrl+P` — Command palette (fuzzy search all commands)
- `d/a/t/r/b` — Quick navigation to screens
- `/` — Search transactions
- `?` — Help overlay
- `q` — Quit

**Vim-style (in lists):**

- `j/k` — Move down/up
- `gg/G` — Jump to top/bottom
- `Ctrl+D/U` — Page down/up

**Actions:**

- `n` — New (transaction/account/budget)
- `f5` — Refresh current view
- `Escape` — Back/Cancel

## Quick Start

### Prerequisites

- Python 3.11 or higher
- Conda (recommended) or pip

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd financial-planning

# Create conda environment (recommended)
conda create -n fin_man python=3.11
conda activate fin_man

# Install dependencies
pip install -e ".[dev]"

# Initialize database
alembic upgrade head

# (Optional) Seed with sample data
python scripts/seed_data.py
```

### Usage

```bash
# Launch the TUI
make run
# or
python -m ledger run

# Export data
python -m ledger export csv -o transactions.csv
python -m ledger export json -o accounts.json
```

## Screenshots

```
┌─────────────────────────────────────────────────────────────────────┐
│ LEDGER TUI                                    Net Worth: $45,230.00 │
├─────────────────────────────────────────────────────────────────────┤
│  [Dashboard]  Accounts  Transactions  Reports  Budgets              │
│                                                                     │
│  ┌─ This Month ──────────────────────────────────────────────────┐  │
│  │   Income      $6,500.00   ████████████████████████████████░░  │  │
│  │   Expenses    $4,230.00   █████████████████████░░░░░░░░░░░░░  │  │
│  │   Savings     $2,270.00   (34.9% rate)                        │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─ Recent Transactions ─────────────────────────────────────────┐  │
│  │  Dec 20  Whole Foods          Expenses:Food:Groceries  -89.34 │  │
│  │  Dec 19  Transfer             Assets:Bank:Savings     +500.00 │  │
│  │  Dec 18  Electric Company     Expenses:Housing:Utils   -67.50 │  │
│  └───────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│ n: new  /: search  ?: help  Ctrl+P: commands  q: quit               │
└─────────────────────────────────────────────────────────────────────┘
```

## Development

### Project Structure

```
financial-planning/
├── src/ledger/
│   ├── cli/              # CLI commands
│   ├── db/               # Database models and migrations
│   ├── repositories/     # Data access layer
│   ├── services/         # Business logic
│   └── tui/              # Textual UI
│       ├── screens/      # Main screens
│       └── widgets/      # Reusable widgets
├── tests/
│   ├── unit/             # Unit tests
│   └── integration/      # Integration tests
├── docs/                 # Documentation
├── scripts/              # Utility scripts
└── data/                 # SQLite database
```

### Commands

```bash
# Run tests
make test
# or: pytest tests/ -v

# Run linter
ruff check src/ledger

# Database migrations
alembic upgrade head      # Apply migrations
alembic revision -m "..."  # Create new migration
```

### Architecture

Layered architecture with clear separation of concerns:

```
TUI/CLI (presentation) → Services (business logic) → Repositories (data access) → Models (ORM)
```

See [docs/architecture.md](docs/architecture.md) for detailed design.

## Double-Entry Accounting

### The Fundamental Equation

```
Assets + Expenses = Liabilities + Equity + Income
```

Every transaction is a journal entry with postings that must sum to zero.

### Account Types

| Type      | Normal Balance | Examples                         |
| --------- | -------------- | -------------------------------- |
| Asset     | Debit (+)      | Bank accounts, investments, cash |
| Liability | Credit (+)     | Credit cards, loans              |
| Equity    | Credit (+)     | Opening balances                 |
| Income    | Credit (+)     | Salary, dividends, interest      |
| Expense   | Debit (+)      | Food, rent, utilities            |

### Account Hierarchy

Accounts use `:` as delimiter for hierarchy:

```
Assets:Bank:Chase:Checking
Expenses:Food:Groceries
Income:Salary
```

## Tech Stack

| Component     | Technology        |
| ------------- | ----------------- |
| Language      | Python 3.11+      |
| TUI Framework | Textual 6.x       |
| Database      | SQLite (WAL mode) |
| ORM           | SQLAlchemy 2.0    |
| Migrations    | Alembic           |
| Testing       | pytest            |

## Roadmap

See [docs/future-features.md](docs/future-features.md) for planned features:

- **v0.3 (Advanced)**: CSV import, recurring transactions, multi-currency
- **v1.0 (Power User)**: Auto-categorization, CLI scripting, plain-text export

## References

- [Textual Documentation](https://textual.textualize.io/)
- [Double-Entry Bookkeeping](https://en.wikipedia.org/wiki/Double-entry_bookkeeping)
- [Ledger CLI](https://www.ledger-cli.org/)
- [Beancount](https://beancount.github.io/)
