.PHONY: install run test migrate migrate-create clean lint format help

help:
	@echo "Ledger TUI - Development Commands"
	@echo ""
	@echo "  make install        Install package in development mode"
	@echo "  make run            Launch TUI application"
	@echo "  make test           Run all tests with coverage"
	@echo "  make migrate        Run database migrations"
	@echo "  make migrate-create Create new migration (use message='description')"
	@echo "  make init-db        Initialize database with sample accounts"
	@echo "  make seed-data      Add sample transactions"
	@echo "  make lint           Run code linter"
	@echo "  make format         Format code with ruff"
	@echo "  make clean          Remove database and Python cache files"

install:
	pip install -e ".[dev]"

run:
	python -m ledger run

test:
	pytest tests/ -v --cov --cov-report=term-missing

migrate:
	alembic upgrade head

migrate-create:
	@if [ -z "$(message)" ]; then \
		echo "Error: Please provide a message with message='description'"; \
		exit 1; \
	fi
	alembic revision --autogenerate -m "$(message)"

init-db:
	python scripts/init_db.py

seed-data:
	python scripts/seed_data.py

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

clean:
	rm -rf data/ledger.db data/ledger.db-*
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name htmlcov -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
