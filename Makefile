.PHONY: dev test dist clean backend-dev frontend-dev backend-test frontend-test lint typecheck

# Development setup
dev: backend-dev frontend-dev

# Backend development
backend-dev:
	cd backend && python -m pip install -e .

# Frontend development
frontend-dev:
	cd frontend && npm install

# Testing
test: backend-test frontend-test

backend-test:
	cd backend && python -m pytest

frontend-test:
	cd frontend && npm test

# Linting and type checking
lint:
	cd backend && python -m ruff check .
	cd frontend && npm run lint

typecheck:
	cd backend && python -m mypy .
	cd frontend && npm run typecheck

# Production build
dist: clean
	cd backend && python -m build
	cd frontend && npm run build

# Clean build artifacts
clean:
	rm -rf backend/dist backend/build backend/*.egg-info
	rm -rf frontend/dist frontend/build

# Start development servers
start-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

start-frontend:
	cd frontend && npm run dev
