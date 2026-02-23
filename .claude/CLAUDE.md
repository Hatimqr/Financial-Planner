# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Ledger TUI** is a terminal-based personal finance tracker built on double-entry accounting principles. It's designed to be local-first, keyboard-driven, and startup-fast (<100ms cold start target).

**Current Version**: v0.3 (MVP Polish — daily-use ready; pyproject.toml still says 0.1.0)

## Tech Stack

- **Language**: Python 3.11+
- **TUI Framework**: Textual 6.x (async, CSS-like styling)
- **Database**: SQLite (single file at `./data/ledger.db`)
- **ORM**: SQLAlchemy 2.0
- **Migrations**: Alembic
- **CLI**: Click
- **Testing**: pytest with coverage

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
│   │   ├── pdf_import_service.py # PDF statement import (in progress)
│   │   ├── pdf_import_models.py  # Data models for PDF import
│   │   ├── seed_demo.py          # Demo data seeding
│   │   └── export_service.py     # CSV/JSON export
│   └── tui/              # Textual TUI application
│       ├── app.py        # Main app, screen navigation, global bindings
│       ├── command_palette.py # Fuzzy command search provider
│       ├── styles.css    # Textual CSS
│       ├── screens/      # 6 screens (dashboard, accounts, transactions, reports, budgets, import_review)
│       └── widgets/      # Modals and overlays (forms, confirm, detail, help, import, import_row_edit)
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

See [docs/database-schema.md](docs/database-schema.md) for the full schema reference with ER diagram, column details, indexes, and design notes.

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

## Key Bindings

**Global:** `/` commands | `d/a/t/r/b` screens | `Ctrl+/` search | `?` help | `q` quit
**Transactions:** `Enter` details | `e` edit | `Backspace` delete | `n` new | `Ctrl+/` search
**Periods:** `1-9` switch | `Tab/S-Tab` cycle | `p` manage

See [docs/keybindings.md](docs/keybindings.md) for the full reference.

## Validation Rules

1. **Balance Check**: Every entry's postings must sum to zero
2. **Account Exists**: All referenced accounts must exist
3. **Type Consistency**: Child accounts must match parent account type
4. **Amount Precision**: Round to 2 decimal places
5. **Different Accounts**: Source and destination cannot be the same

## In-Progress Work

- **PDF Import**: `pdf_import_service.py` + `import_review` screen — importing bank PDF statements (uncommitted, actively developed)

## Future Development

See [docs/future-features.md](docs/future-features.md) for planned features.
