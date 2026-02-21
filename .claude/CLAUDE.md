# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Ledger TUI** is a terminal-based personal finance tracker built on double-entry accounting principles. It's designed to be local-first, keyboard-driven, and startup-fast (<100ms cold start target).

**Current Version**: v0.3 (MVP Polish — daily-use ready)

## Tech Stack

- **Language**: Python 3.11+
- **TUI Framework**: Textual 6.x (async, CSS-like styling)
- **Database**: SQLite (single file at `./data/ledger.db`)
- **ORM**: SQLAlchemy 2.0
- **Migrations**: Alembic
- **CLI**: Click
- **Testing**: pytest with coverage (69 tests, ~1.3s)

## Project Structure

```
financial-planning/
├── src/ledger/
│   ├── cli/              # CLI commands (run, add, import, export, init, seed)
│   ├── db/               # Database models, connection, migrations
│   │   └── migrations/   # Alembic migration scripts
│   ├── repositories/     # Data access layer (base, account, entry, posting)
│   ├── services/         # Business logic layer
│   │   ├── account_service.py    # Account CRUD, hierarchy, balance
│   │   ├── transaction_service.py # Double-entry CRUD + validation
│   │   ├── budget_service.py     # Budget management + progress
│   │   ├── report_service.py     # KPIs, income statement, balance sheet
│   │   ├── import_service.py     # CSV import with preview + dedup
│   │   └── export_service.py     # CSV/JSON export
│   └── tui/              # Textual TUI application
│       ├── app.py        # Main app, screen navigation, global bindings
│       ├── command_palette.py # Fuzzy command search provider
│       ├── styles.css    # Textual CSS
│       ├── screens/      # 5 main screens (dashboard, accounts, transactions, reports, budgets)
│       └── widgets/      # Modals and overlays (forms, confirm, detail, help, import)
├── tests/
│   ├── unit/             # Unit tests (models, repos, services, import)
│   └── integration/      # End-to-end flow tests
├── docs/                 # Documentation (architecture, requirements, future features)
├── scripts/              # Utility scripts (init_db, seed_data)
└── data/                 # SQLite database storage
```

## Architecture

### Layered Architecture

```
TUI/CLI Layer (presentation)
    ↓
Service Layer (business logic, validation)
    ↓
Repository Layer (data access, queries)
    ↓
Database Layer (SQLAlchemy models, SQLite)
```

### Key Patterns

- **Screen Navigation**: `_switch_main_screen()` pops all stacked screens before pushing new one (prevents infinite stacking). Modals use `push_screen`.
- **Common Interface**: All screens implement `refresh_data()` for consistent refresh behavior.
- **Balance Validation**: Service layer validates postings sum to zero (not DB triggers — triggers cause false positives with multi-posting inserts).
- **Account Hierarchy**: Tree structure using `:` as delimiter. Parent accounts auto-created as placeholders.

### Database Schema

Four core tables:
1. **accounts** — Account hierarchy with full path names, types, placeholder flag
2. **entries** — Journal entry headers (date, description, payee, status)
3. **postings** — Line items linking entries to accounts with amounts (positive=debit, negative=credit)
4. **budgets** — Category budgets by period (monthly, quarterly, yearly)

## Development Commands

```bash
# Setup environment
conda create -n fin_man python=3.11
conda activate fin_man
pip install -e ".[dev]"

# Run the application
make run                  # or: python -m ledger run

# Quick-add a transaction from CLI
python -m ledger add "Coffee" 5.50 --from checking --to food

# Import a bank CSV
python -m ledger import bank.csv --from checking --to food

# Run tests
make test                 # or: pytest tests/ -v

# Database migrations
alembic upgrade head

# Linting
ruff check src/ledger
```

## Current Features (v0.3)

### Screens
- **Dashboard** (`d`): Net worth, income/expenses KPIs, recent transactions, expense breakdown
- **Accounts** (`a`): Hierarchical account list with balances
- **Transactions** (`t`): Transaction list with date filtering, search, edit, detail view, delete
- **Reports** (`r`): Income Statement and Balance Sheet with period selection
- **Budgets** (`b`): Budget progress with visual progress bars

### Key Bindings

**Global:** `Ctrl+P` commands | `d/a/t/r/b` screens | `/` search | `?` help | `q` quit

**Transaction List:** `Enter` view details | `e` edit | `Delete` delete | `n` new | `j/k` nav

**Vim-style:** `j/k` down/up | `gg/G` top/bottom | `Ctrl+D/U` page

### Services

- **AccountService**: Account CRUD, hierarchy, balance, search, suggestions
- **TransactionService**: Create, update, delete transactions with double-entry validation
- **BudgetService**: Budget management and progress tracking
- **ReportService**: Financial reports, KPIs, transaction search
- **ImportService**: CSV import with bank presets, preview, duplicate detection
- **ExportService**: CSV/JSON export

### CLI Commands

- `ledger run` — Launch TUI
- `ledger add` — Quick-add transaction (`-f`/`-t` for from/to accounts)
- `ledger import` — Import CSV (supports `--format generic|chase|bofa`)
- `ledger export` — Export to CSV/JSON
- `ledger init` — Initialize database
- `ledger seed` — Add sample data

## Testing

```bash
pytest tests/ -v                              # All 69 tests
pytest tests/unit/test_services.py -v         # Service tests
pytest tests/unit/test_import_service.py -v   # Import tests
pytest tests/ --cov=src/ledger --cov-report=html  # Coverage report
```

## Validation Rules

1. **Balance Check**: Every entry's postings must sum to zero
2. **Account Exists**: All referenced accounts must exist
3. **Type Consistency**: Child accounts must match parent account type
4. **Amount Precision**: Round to 2 decimal places
5. **Different Accounts**: Source and destination cannot be the same

## Future Development

See [docs/future-features.md](docs/future-features.md) for planned features: recurring transactions, auto-categorization, multi-currency, and more.

## References

- [Textual Documentation](https://textual.textualize.io/)
- [Ledger CLI](https://www.ledger-cli.org/) — Inspiration for plain-text accounting
- [Beancount](https://beancount.github.io/) — Python-based plain-text accounting
- [Full Requirements](docs/requirements.md)
