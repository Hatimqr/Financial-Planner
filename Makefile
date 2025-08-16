.PHONY: dev dev-parallel test test-unit test-integration test-frontend test-browser clean install start db-init db-seed db-reset db-drop

# Development targets
dev: dev-parallel

dev-parallel:
	@echo "🚀 Starting Financial Planning App..."
	@echo "Backend: http://localhost:8000"
	@echo "Frontend: http://localhost:5173"
	@echo "Press Ctrl+C to stop both servers"
	@bash -c 'trap "kill 0" EXIT; cd backend && python main.py & cd frontend && npm run dev'

dev-backend:
	@echo "Starting backend development server..."
	cd backend && python main.py

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

# Database targets
db-init:
	@echo "Initializing database..."
	cd backend && python -c "from app.db import Base, engine; Base.metadata.create_all(bind=engine); print('Database tables created successfully!')"

db-seed:
	@echo "Seeding database with sample data..."
	cd backend && python app/seeds/seed_v1.py

db-reset:
	@echo "Resetting database..."
	cd backend && /opt/anaconda3/envs/zone_detect/bin/python utils/reset_db.py

db-drop:
	@echo "Dropping database tables..."
	cd backend && python -c "from app.db import Base, engine; Base.metadata.drop_all(bind=engine); print('Database tables dropped successfully!')"

# Test targets
test: test-unit test-integration test-frontend
	@echo "✅ All tests completed successfully!"

test-unit:
	@echo "🧪 Running unit tests..."
	cd backend && /opt/anaconda3/envs/zone_detect/bin/python -m pytest tests/ -v --ignore=tests/test_frontend_integration.py

test-integration:
	@echo "🔗 Running integration tests..."
	cd backend && /opt/anaconda3/envs/zone_detect/bin/python -m pytest tests/test_*integration*.py -v

test-frontend:
	@echo "🌐 Running frontend integration tests..."
	cd backend && ./tests/frontend/test_frontend.sh

test-browser:
	@echo "🖥️  Starting browser test server..."
	@echo "📋 Open http://localhost:5175/tests/frontend/test_frontend_browser.html in your browser"
	@echo "🛑 Press Ctrl+C to stop the server"
	cd backend && /opt/anaconda3/envs/zone_detect/bin/python tests/frontend/serve_test.py

test-fast:
	@echo "⚡ Running fast tests only..."
	cd backend && /opt/anaconda3/envs/zone_detect/bin/python -m pytest tests/ -q --ignore=tests/test_frontend_integration.py

# Cleanup
clean:
	@echo "Cleaning up build artifacts..."
	rm -rf frontend/dist
	rm -rf backend/__pycache__
	rm -rf backend/app/__pycache__
	rm -rf backend/.pytest_cache
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +

# Simple start alias
start: dev

# Help
help:
	@echo "Available targets:"
	@echo "  dev          - 🚀 Start both backend and frontend (recommended)"
	@echo "  start        - Alias for dev"
	@echo "  dev-backend  - Start only backend development server"
	@echo "  dev-frontend - Start only frontend development server"
	@echo "  install      - Install all dependencies"
	@echo "  clean        - Clean up build artifacts"
	@echo ""
	@echo "Test commands:"
	@echo "  test         - 🧪 Run all tests (unit + integration + frontend)"
	@echo "  test-unit    - 🔬 Run unit tests only"
	@echo "  test-integration - 🔗 Run integration tests only"
	@echo "  test-frontend - 🌐 Run frontend API integration tests"
	@echo "  test-browser - 🖥️  Start browser-based test server"
	@echo "  test-fast    - ⚡ Run fast tests only (excludes slow integration tests)"
	@echo ""
	@echo "Database commands:"
	@echo "  db-init      - Initialize database (create tables)"
	@echo "  db-seed      - Seed database with sample data"
	@echo "  db-reset     - Reset database (drop, init, seed)"
	@echo "  db-drop      - Drop all database tables"
	@echo ""
	@echo "  help         - Show this help message"
	@echo ""
	@echo "Quick start: make dev"
	@echo "This will start both servers:"
	@echo "  Frontend: http://localhost:5173 (or 5174)"
	@echo "  Backend API: http://localhost:8000"
	@echo "  Database tables are auto-created on first run"