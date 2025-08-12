# Local-First Investment Planner & Portfolio Analytics

This project is a local-first investment tracking and portfolio management tool built with Python (FastAPI) backend and React frontend, using SQLite for data storage.

## Project Structure

```
backend/          # Python FastAPI application
  app/            # Main application code (routers, services, repositories, models)
  adapters/       # Price/FX/broker data adapters
  tests/          # Unit tests
frontend/         # React + Vite application
  src/            # Source code (pages, components, hooks, api)
data/             # SQLite database location
docs/             # Project documentation
```

## Development Commands

### Setup
```bash
# Initialize project structure
make dev

# Install backend dependencies
cd backend
poetry install
# or
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
```

### API Documentation
- **Full API Docs**: [api-endpoints.md](./api-endpoints.md)
- **Auto-generated Docs**: http://localhost:8000/docs (when server running)
- **30+ Endpoints**: Accounts, Instruments, Transactions, Corporate Actions, Portfolio

### Development
```bash
# Start backend server
cd backend
uvicorn main:app --reload

# Start frontend development server
cd frontend
npm run dev

# Run tests
make test

# Lint and type checking
npm run lint        # Frontend
npm run typecheck   # Frontend
# Add backend linting commands as needed
```

### Build and Distribution
```bash
# Build production version
make dist
```

## Key Features

- **Double-entry accounting** with balanced transactions
- **Multiple account types**: Assets, Liabilities, Income, Expenses, Equity
- **Portfolio management** with target allocations and rebalancing
- **Performance analytics**: TWR, IRR, risk metrics, benchmark comparisons
- **Multi-currency support** with FX rate handling
- **Local-first**: All data stored in SQLite, optional network adapters
- **Import/Export**: CSV/XLSX support for trades, prices, positions

## Architecture

- **Backend**: FastAPI + SQLAlchemy + Alembic migrations
- **Frontend**: React + Vite with TypeScript
- **Database**: SQLite with double-entry journal structure
- **Data Privacy**: Local storage by default, optional encrypted backups

## Development Status

**Epic 0 - Project Setup**: ✅ Complete
- Project scaffold with FastAPI backend and React frontend
- Development environment with Makefile targets
- Configuration system with YAML and environment variables
- Logging and structured error handling

**Epic 1 - Data Model & Migrations**: ✅ Complete  
- SQLite schema with double-entry accounting structure
- Alembic migrations with triggers and constraints
- SQLAlchemy ORM models with relationships
- Database seeding and comprehensive test suite
- 38/39 tests passing with full schema validation

**Epic 2 - Core Accounting Engine**: 🚧 In Progress
- Double-entry journal service with balance validation
- FIFO lot engine for cost basis tracking
- Corporate actions processing (splits, dividends)
- Realized/unrealized P&L calculations
- Position reconciliation from lots

See docs/checklist.md for detailed progress tracking across all 16 epics.

## Testing

Maintain ≥80% unit test coverage for core services. All analytics calculations must pass acceptance tests against reference datasets.

## Local-First Principles

- All data stored locally in SQLite
- No network calls by default (adapters optional and user-enabled)
- Deterministic exports and backups
- Graceful offline operation