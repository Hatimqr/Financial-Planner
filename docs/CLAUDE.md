# Local-First Investment Planner & Portfolio Analytics - MVP

This project is a local-first investment tracking and portfolio management tool built with Python (FastAPI) backend and React frontend, using SQLite for data storage.

## Current Focus: MVP Development

We are currently building the **Minimum Viable Product (MVP)** which focuses on core double-entry accounting functionality with a clean, utilitarian interface. The MVP includes basic transaction management, account ledgers, and a dashboard view.

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
- **Current API Docs**: [api-endpoints.md](./api-endpoints.md)
- **Auto-generated Docs**: http://localhost:8000/docs (when server running)
- **MVP Focus**: Core endpoints for Accounts, Transactions, and Dashboard functionality

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

## MVP Key Features

- **Double-entry accounting** with balanced transactions (Core implementation)
- **Multiple account types**: Assets, Liabilities, Income, Expenses, Equity
- **Account management**: Create, view, edit, delete accounts
- **Transaction management**: Create and view double-entry transactions
- **Dashboard**: Net worth display, account summaries, time-series visualization
- **T-Account view**: Classic ledger interface for transaction details
- **Local-first**: All data stored in SQLite, no network dependencies

## Future Features (Post-MVP)
- Portfolio management with target allocations and rebalancing
- Performance analytics: TWR, IRR, risk metrics, benchmark comparisons
- Multi-currency support with FX rate handling
- Import/Export: CSV/XLSX support for trades, prices, positions
- Goal planning and Monte Carlo simulations

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

**Epic 2 - MVP Backend Development**: ✅ Complete
- Full CRUD operations for accounts, transactions, instruments, and corporate actions
- Comprehensive dashboard endpoints (summary, timeseries, ledger views)
- Double-entry transaction validation and posting
- Balance calculation and aggregation services with date filtering
- All DELETE endpoints implemented with proper validation

**Epic 3 - Frontend UI Enhancement**: 🚧 In Progress
- Frontend UI overhaul focused on visual design and styling improvements
- Maintaining existing app layout structure and functionality

See docs/checklist.md for detailed progress tracking and docs/UX-design.md for UI specifications.

## Testing

Maintain ≥80% unit test coverage for core services. All analytics calculations must pass acceptance tests against reference datasets.

## Local-First Principles

- All data stored locally in SQLite
- No network calls by default (adapters optional and user-enabled)
- Deterministic exports and backups
- Graceful offline operation