.PHONY: dev test dist clean install db-init db-seed db-reset

# Development targets
dev: dev-backend dev-frontend

dev-backend:
	@echo "Starting backend development server..."
	cd backend && python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	@echo "Starting frontend development server..."
	cd frontend && npm run dev

# Install dependencies
install: install-backend install-frontend

install-backend:
	@echo "Installing backend dependencies..."
	cd backend && pip install -r requirements.txt

install-frontend:
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

# Test targets (placeholder)
test: test-backend test-frontend

test-backend:
	@echo "Running backend tests..."
	cd backend && python -m pytest -q

test-frontend:
	@echo "Running frontend tests..."
	@echo "TODO: Add frontend test command"

# Distribution/Production build targets (placeholder)
dist: dist-backend dist-frontend

dist-backend:
	@echo "Building backend for production..."
	@echo "TODO: Add backend production build command"

dist-frontend:
	@echo "Building frontend for production..."
	cd frontend && npm run build

# Cleanup
clean:
	@echo "Cleaning up build artifacts..."
	rm -rf frontend/dist
	rm -rf backend/__pycache__
	rm -rf backend/app/__pycache__
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +

# Database targets
db-init:
	@echo "Initializing database..."
	@mkdir -p data
	cd backend && alembic upgrade head

db-seed:
	@echo "Seeding database..."
	cd backend && python -m app.seeds.seed_v1

db-reset: 
	@echo "Resetting database..."
	rm -f data/app.db
	$(MAKE) db-init
	$(MAKE) db-seed

# Help
help:
	@echo "Available targets:"
	@echo "  dev          - Start both backend and frontend in development mode"
	@echo "  dev-backend  - Start only backend development server"
	@echo "  dev-frontend - Start only frontend development server"
	@echo "  install      - Install all dependencies"
	@echo "  test         - Run all tests"
	@echo "  dist         - Build for production"
	@echo "  clean        - Clean up build artifacts"
	@echo "  db-init      - Initialize database with migrations"
	@echo "  db-seed      - Seed database with initial data"
	@echo "  db-reset     - Reset database (drop, init, seed)"
	@echo "  help         - Show this help message"