# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Ledger TUI** is a terminal-based personal finance tracker built on double-entry accounting principles. It's designed to be local-first, keyboard-driven, and startup-fast (<100ms cold start target).

Think: Claude Code meets accounting.

**Current Version**: v0.2 (Core features complete)

## Tech Stack

- **Language**: Python 3.11+
- **TUI Framework**: Textual 6.x (async, CSS-like styling)
- **Database**: SQLite (single file at `./data/ledger.db`)
- **ORM**: SQLAlchemy 2.0
- **Migrations**: Alembic
- **Testing**: pytest with coverage

## Project Structure

```
financial-planning/
├── src/ledger/
│   ├── cli/              # CLI commands (ledger run, etc.)
│   ├── db/               # Database models, connection, migrations
│   │   └── migrations/   # Alembic migration scripts
│   ├── repositories/     # Data access layer
│   ├── services/         # Business logic layer
│   └── tui/              # Textual TUI application
│       ├── screens/      # Main screens (dashboard, accounts, etc.)
│       └── widgets/      # Reusable widgets (forms, modals)
├── tests/
│   ├── unit/             # Unit tests for models, repos, services
│   └── integration/      # End-to-end flow tests
├── docs/                 # Documentation
├── scripts/              # Utility scripts
└── data/                 # SQLite database storage
```

## Architecture

### Layered Architecture

```
TUI/CLI Layer (presentation)
    ↓
Service Layer (business logic)
    ↓
Repository Layer (data access)
    ↓
Database Layer (SQLAlchemy models)
```

### Double-Entry Accounting Model

The fundamental equation: `Assets + Expenses = Liabilities + Equity + Income`

Every transaction is a **journal entry** containing two or more **postings** (line items) that must sum to zero (debits = credits). Validation is performed in the service layer.

**Account Types and Normal Balances:**
- **Asset**: Debit (+) — Bank accounts, investments, cash
- **Liability**: Credit (+) — Credit cards, loans
- **Equity**: Credit (+) — Opening balances, retained earnings
- **Income**: Credit (+) — Salary, dividends, interest
- **Expense**: Debit (+) — Food, rent, utilities

**Account Hierarchy:** Tree structure using `:` as delimiter (e.g., `Assets:Bank:Chase:Checking`)

### Database Schema

Four core tables:
1. **accounts** — Account hierarchy with full path names
2. **entries** — Journal entry headers (date, description, payee, status)
3. **postings** — Line items linking entries to accounts with amounts
4. **budgets** — Category budgets by period (monthly, quarterly, yearly)

## Development Commands

```bash
# Setup environment
conda create -n fin_man python=3.11
conda activate fin_man
pip install -e ".[dev]"

# Run the application
make run                  # or: python -m ledger run

# Run tests
make test                 # or: pytest tests/ -v

# Database migrations
alembic upgrade head      # Apply migrations
alembic current           # Check current revision

# Linting
ruff check src/ledger
```

## Current Features (v0.2)

### Screens
- **Dashboard** (`d`): Net worth, income/expenses KPIs, recent transactions, expense breakdown
- **Accounts** (`a`): Hierarchical account list with balances
- **Transactions** (`t`): Transaction list with date filtering, search
- **Reports** (`r`): Income Statement and Balance Sheet
- **Budgets** (`b`): Budget progress with visual progress bars

### Key Bindings

**Global Navigation:**
- `Ctrl+P` — Command palette (fuzzy search all commands)
- `d/a/t/r/b` — Quick navigation to screens
- `g d/a/t/r/b` — Vim-style go-to navigation
- `/` — Search transactions
- `?` — Help
- `q` — Quit

**In Lists:**
- `j/k` — Down/Up
- `gg/G` — Top/Bottom
- `Ctrl+D/U` — Page down/up

**Actions:**
- `n` — New (transaction/account/budget depending on screen)
- `f5` — Refresh current view
- `Escape` — Back/Cancel

### Services

- **AccountService**: Account CRUD, hierarchy management, balance calculations
- **TransactionService**: Double-entry transaction creation and validation
- **BudgetService**: Budget management and progress tracking
- **ReportService**: Financial reports (income statement, balance sheet, KPIs)
- **ExportService**: CSV/JSON export functionality

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src/ledger --cov-report=html

# Run specific test file
pytest tests/unit/test_services.py -v
```

Current test coverage: 60 tests covering models, repositories, services, and integration flows.

## Validation Rules

1. **Balance Check**: Every entry's postings must sum to zero
2. **Account Exists**: All referenced accounts must exist
3. **Type Consistency**: Child accounts must match parent account type
4. **Amount Precision**: Round to 2 decimal places

## Future Development

See [docs/future-features.md](docs/future-features.md) for planned Advanced (v0.3) and Power User (v1.0) features.

## References

- [Textual Documentation](https://textual.textualize.io/)
- [Ledger CLI](https://www.ledger-cli.org/) — Inspiration for plain-text accounting
- [Beancount](https://beancount.github.io/) — Python-based plain-text accounting
- [Full Requirements](docs/requirements.md)
