# Gemini Project Analysis: Financial Planning

This document provides a summary of the Financial Planning project based on an analysis of the codebase.

## Project Overview

The "Financial Planning" project is a local-first, privacy-focused application designed for investment tracking, portfolio analysis, and allocation planning. It runs entirely on the user's local machine, with optional data adapters for fetching external data like stock prices.

The application is composed of a Python backend and a React frontend.

### Key Features

*   **Local-First:** All data is stored locally in a SQLite database.
*   **Privacy-Focused:** No data is sent to external servers by default.
*   **Investment Tracking:** Track investment activity through a double-entry accounting system.
*   **Portfolio Analytics:** Analyze portfolio performance with metrics like Time-Weighted Return (TWR) and Internal Rate of Return (IRR).
*   **Allocation Planning:** Plan and rebalance investment allocations based on defined targets.
*   **Data Import/Export:** Import and export data via CSV files.

## Architecture

The project follows a client-server architecture:

*   **Backend:** A Python-based API built with the **FastAPI** framework. It uses **SQLAlchemy** for database interaction and **SQLite** as the database.
*   **Frontend:** A single-page application built with **React** and **TypeScript**, using **Vite** for the development server and build tooling.

## Codebase Structure

```
/
├── backend/        # Python FastAPI backend
│   ├── app/        # Main application code
│   ├── tests/      # Backend tests
│   └── pyproject.toml # Backend dependencies
├── frontend/       # React/TypeScript frontend
│   ├── src/        # Frontend source code
│   ├── tests/      # Frontend tests
│   └── package.json # Frontend dependencies
├── data/           # Application data (SQLite DB, logs)
├── docs/           # Project documentation
├── config.yaml     # Application configuration
└── Makefile        # Development and build commands
```

## Development

The `Makefile` provides several commands for development and testing:

*   `make dev`: Sets up the development environment.
*   `make test`: Runs backend and frontend tests.
*   `make lint`: Lints the backend and frontend code.
*   `make typecheck`: Type-checks the backend and frontend code.
*   `make start-backend`: Starts the backend development server.
*   `make start-frontend`: Starts the frontend development server.

## Project Status

The project is currently in the initial setup phase, as indicated in `docs/checklist.md`. The basic project structure is in place, but most of the core features are yet to be implemented.
