# Financial Planning Application

A local-first investment tracking and portfolio management tool built with Python (FastAPI) backend and React frontend.

## 🚀 Quick Start

```bash
# Start both backend and frontend
make dev

# Or start individually
make dev-backend   # Backend only: http://localhost:8000
make dev-frontend  # Frontend only: http://localhost:5173
```

## 📋 Prerequisites

- Python 3.11+ with conda environment `zone_detect`
- Node.js 18+ and npm
- SQLite (included with Python)

## 🧪 Testing

```bash
# Run all tests
make test

# Run specific test types
make test-unit        # Unit tests only (fastest)
make test-integration # Integration tests
make test-frontend    # Frontend API integration tests
make test-browser     # Interactive browser testing
```

## 📁 Project Structure

```
├── backend/                 # Python FastAPI application
│   ├── app/                # Main application code
│   │   ├── routers/        # API endpoints
│   │   ├── services/       # Business logic
│   │   ├── repositories/   # Data access layer
│   │   ├── models.py       # SQLAlchemy models
│   │   └── ...
│   ├── tests/              # Backend tests
│   │   ├── services/       # Service tests
│   │   ├── frontend/       # Frontend integration tests
│   │   └── ...
│   ├── utils/              # Utility scripts
│   └── data/               # SQLite database
├── frontend/               # React + TypeScript application
│   ├── src/
│   │   ├── pages/         # Page components
│   │   ├── components/    # Reusable components
│   │   ├── services/      # API client
│   │   └── types/         # TypeScript interfaces
├── docs/                   # Documentation
└── Makefile               # Development commands
```

## ✨ Features

- **Double-entry accounting** with balanced transactions
- **Account management** for Assets, Liabilities, Income, Expenses, Equity
- **Transaction tracking** with T-account ledger views
- **Dashboard** with net worth and time-series visualization
- **Local-first** - all data stored in SQLite

## 🔧 Available Commands

### Development
- `make dev` - Start both frontend and backend
- `make dev-backend` - Start backend only
- `make dev-frontend` - Start frontend only
- `make install` - Install all dependencies

### Database
- `make db-reset` - Reset database with fresh data
- `make db-seed` - Add sample data
- `make db-init` - Initialize empty database

### Testing
- `make test` - Run all tests
- `make test-unit` - Unit tests only
- `make test-integration` - Integration tests
- `make test-frontend` - Frontend API tests
- `make test-browser` - Interactive browser tests

### Utilities
- `make clean` - Clean build artifacts
- `make help` - Show all available commands

## 🌐 API Documentation

- **Interactive docs**: http://localhost:8000/docs (when backend running)
- **Health check**: http://localhost:8000/health

## 🏗️ Architecture

- **Backend**: FastAPI + SQLAlchemy + SQLite
- **Frontend**: React + TypeScript + Vite
- **Testing**: pytest + custom integration tests
- **Development**: Make-based workflow

## 📊 Current Status

✅ **Backend MVP Complete**
- Account management API
- Transaction management with double-entry validation
- Dashboard with time-series data
- Comprehensive test suite (121 tests passing)

✅ **Frontend MVP Complete**
- Dashboard with net worth visualization
- Account management interface
- Transaction ledger views
- Full integration with backend APIs

✅ **Testing Infrastructure**
- Unit tests for all services
- Integration tests for API endpoints
- Frontend integration testing
- Browser-based testing tools