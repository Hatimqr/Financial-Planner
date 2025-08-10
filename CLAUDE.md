# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Local-First Investment Planner & Portfolio Analytics** tool - a privacy-focused application for tracking investment activity, analyzing portfolio performance, and planning allocations. The system runs entirely locally with optional data adapters.

Refer to `docs/description.md` for project description

## Architecture

### Backend (Python FastAPI)

- **Location**: `/backend` directory
- **Stack**: FastAPI + SQLAlchemy + Alembic migrations
- **Database**: SQLite (`./data/app.db`)
- **Start**: `uvicorn main:app --reload`
- **API Base**: `http://localhost:8000/api`

### Frontend (React)

- **Location**: `/frontend` directory
- **Stack**: React + Vite
- **Start**: `npm run dev`

### Key Architecture Principles

- **Double-entry accounting**: All transactions must balance (sum of transaction_lines.amount = 0)
- **Local-first**: No network calls by default, optional adapters for prices/FX
- **Multi-currency**: Base currency with FX curves, per-instrument currency support
- **Lot tracking**: FIFO cost basis with per-lot tracking for realized/unrealized P/L

## Core Data Model (SQLite)

Key tables and relationships:

- **accounts**: Account hierarchy (portfolios, brokerages, etc.)
- **instruments**: Stocks, ETFs, bonds, crypto, cash
- **transactions/transaction_lines**: Double-entry journal entries
- **lots**: Cost basis tracking with FIFO method
- **prices/fx_rates**: Price and FX data store
- **corporate_actions**: Splits, dividends, mergers
- **targets**: Portfolio allocation targets with rebalancing bands

## Common Development Commands

Based on the project structure, use these standard commands:

**Backend Development:**

```bash
cd backend
uvicorn main:app --reload
```

**Frontend Development:**

```bash
cd frontend
npm run dev
```

**Build & Test:**

```bash
make dev        # Development setup
make test       # Run test suite
make dist       # Production build
```

## Key Business Logic

### Transaction Processing

- All transactions must balance in base currency
- Corporate actions generate journal entries automatically
- Multi-currency transactions use FX rates on transaction date

### Performance Calculations

- **TWR**: Time-weighted return with cashflow breaks
- **IRR/XIRR**: Money-weighted return solving NPV = 0
- **Risk metrics**: Volatility, Sharpe, Sortino, max drawdown, beta vs benchmark

### Rebalancing Engine

- Detects drift vs target allocations
- Generates trade proposals respecting bands and minimum trade sizes
- Supports tax lot selection methods

## Development Phases

The project follows this epic structure:

- **M0**: Project setup, data model, migrations
- **M1**: Core accounting engine, instruments, basic CRUD
- **M2**: Analytics, performance calculations, dashboard
- **M3**: Rebalancing, cashflow planning, imports/exports
- **M4**: Goal planning, CLI, security features

Refer to `docs/checklist.md` for detailed epic breakdown and current status.

## Important Constraints

- **Offline-first**: Ensure all core functionality works without network
- **Accounting correctness**: Transactions must always balance
- **Position reconciliation**: Current positions must always reconcile to lot history
- **Multi-currency integrity**: FX translations must be consistent across reports
