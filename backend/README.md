# Financial Planning Backend

This is the backend API for the local-first investment planner and portfolio analytics application.

## Features Implemented

### EP0-4: Base Configuration System (`app/config.py`)
- Pydantic-based configuration with YAML file support
- Environment variable overrides
- Local-first principles (adapters disabled by default)
- Database, API, logging, and adapter configuration sections

### EP0-5: Logging and Error Handling

- **Structured Logging** (`app/logging.py`):
  - JSON-structured logs for file output
  - Human-readable console output
  - Configurable log levels via configuration
  - Request ID tracing
  - Helper functions for request and error logging

- **Error Handling** (`app/errors.py`):
  - Standardized error envelope format: `{"ok": false, "error": {...}}`
  - Custom exception classes for common scenarios
  - FastAPI exception handlers
  - Request ID tracking for debugging

- **Main Application** (`main.py`):
  - FastAPI app with configuration-driven initialization
  - Exception handler registration
  - Request logging middleware
  - CORS configuration
  - Health check endpoints

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the development server:
   ```bash
   python main.py
   ```

3. Visit http://127.0.0.1:8000 for the API
   - `/`: Basic status endpoint
   - `/health`: Health check
   - `/api/status`: API feature status
   - `/test-error`: Test error handling
   - `/docs`: Auto-generated API documentation

## Testing

Run the test suite:
```bash
pytest
```

## Configuration

Configuration is managed through `config.yaml` and environment variables:

- **YAML file**: `config.yaml` (created automatically with defaults)
- **Environment variables**: Use `APP__SECTION__KEY` format (e.g., `APP__API__PORT=8080`)
- **Local-first**: All adapters are disabled by default

### Configuration Sections:
- `database`: SQLite database settings
- `api`: Server host, port, debug settings
- `logging`: Log levels, file paths, rotation
- `app`: Timezone, currency, backup settings
- `adapters`: Price, FX, and broker import adapters (disabled by default)

## Logging

Logs are written to:
- Console: Human-readable format
- File: Configured path (default: `data/logs/app.log`) in structured JSON format

Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL (configurable)

## Error Format

All API errors follow this envelope format:

```json
{
  "ok": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {
      "additional": "context"
    }
  },
  "request_id": "uuid-for-tracing"
}
```

## Directory Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── config.py       # Configuration management
│   ├── logging.py      # Structured logging system
│   ├── errors.py       # Error handling and custom exceptions
│   ├── models/         # Future: Database models
│   ├── services/       # Future: Business logic services
│   ├── repositories/   # Future: Data access layer
│   └── routers/        # Future: API route handlers
├── adapters/           # Future: External data adapters
├── tests/
│   ├── __init__.py
│   ├── test_logging.py
│   └── test_errors.py
├── data/               # Data directory (logs, database)
├── main.py            # FastAPI application
├── config.yaml        # Configuration file
├── requirements.txt   # Python dependencies
├── pytest.ini        # Test configuration
└── README.md         # This file
```

## Next Steps

Future epic implementations will add:
- Database models and migrations (EP1)
- Core accounting engine (EP2)
- API endpoints for CRUD operations (EP9)
- Frontend integration points