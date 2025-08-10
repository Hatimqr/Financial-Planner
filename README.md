# Financial Planning

Local-First Investment Planner & Portfolio Analytics

A privacy-focused application for tracking investment activity, analyzing portfolio performance, and planning allocations. The system runs entirely locally with optional data adapters.

## Quick Start

### Development Setup

1. **Install dependencies:**
   ```bash
   python setup.py
   ```

2. **Start backend server:**
   ```bash
   make start-backend
   ```

3. **Start frontend server (in another terminal):**
   ```bash
   make start-frontend
   ```

4. **Access the application:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API docs: http://localhost:8000/docs

### Alternative Setup

**Backend:**
```bash
cd backend
pip install -e .
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Development Commands

- `make dev` - Set up development environment
- `make test` - Run all tests
- `make lint` - Run linting
- `make typecheck` - Run type checking
- `make dist` - Build for production

## Architecture

- **Backend**: Python FastAPI + SQLAlchemy + SQLite
- **Frontend**: React + TypeScript + Vite
- **Data**: Local SQLite database with optional external adapters

## Configuration

Edit `config.yaml` to customize settings. Key sections:
- Database path and settings
- API server configuration
- Logging preferences
- Security options

## Project Status

Currently implementing Epic 0 (Project Setup). See `docs/checklist.md` for detailed development roadmap.
