# API Endpoints Documentation

**Financial Planning API v0.1.0**  
*Local-first investment planner and portfolio analytics*

---

## Base URL
```
http://localhost:8000
```

## Authentication
Currently no authentication required (local-first application).

---

## System Endpoints

### Health Check
```http
GET /
```
Basic health check for the service.

**Response:**
```json
{
  "ok": true,
  "service": "Financial Planning API",
  "version": "0.1.0", 
  "status": "running"
}
```

### API Status
```http
GET /api/status
```
Detailed API status and feature information.

**Response:**
```json
{
  "ok": true,
  "api_version": "v1",
  "features": {
    "logging": true,
    "error_handling": true,
    "request_tracing": true
  }
}
```

---

## Accounts API

Manage investment accounts (cash, brokerage, retirement, etc.).

### List Accounts
```http
GET /api/accounts/
```

**Query Parameters:**
- `type` (optional): Filter by account type (`ASSET`, `LIABILITY`, `EQUITY`, `INCOME`, `EXPENSE`)
- `currency` (optional): Filter by currency (e.g., `USD`)

**Response:**
```json
[
  {
    "id": 1,
    "name": "Assets:Brokerage",
    "type": "ASSET",
    "currency": "USD",
    "created_at": "2023-12-01T10:00:00Z"
  }
]
```

### Get Account
```http
GET /api/accounts/{account_id}
```

**Response:**
```json
{
  "id": 1,
  "name": "Assets:Brokerage",
  "type": "ASSET", 
  "currency": "USD",
  "created_at": "2023-12-01T10:00:00Z"
}
```

### Create Account
```http
POST /api/accounts/
```

**Request Body:**
```json
{
  "name": "Assets:Retirement IRA",
  "type": "ASSET",
  "currency": "USD"
}
```

**Valid Account Types:**
- `ASSET` - Asset accounts (cash, brokerage, retirement)
- `LIABILITY` - Liability accounts (loans, credit cards)
- `EQUITY` - Equity accounts (opening balances)
- `INCOME` - Income accounts (dividends, interest)
- `EXPENSE` - Expense accounts (fees, taxes)

### Update Account
```http
PUT /api/accounts/{account_id}
```

**Request Body:**
```json
{
  "name": "Assets:Roth IRA",
  "type": "ASSET",
  "currency": "USD"
}
```

### Delete Account
```http
DELETE /api/accounts/{account_id}
```

**Response:**
```json
{
  "ok": true,
  "message": "Account deleted successfully"
}
```

---

## Instruments API

Manage tradable securities (stocks, ETFs, bonds, etc.).

### List Instruments
```http
GET /api/instruments/
```

**Query Parameters:**
- `symbol` (optional): Filter by symbol (partial match)
- `type` (optional): Filter by instrument type
- `currency` (optional): Filter by currency
- `limit` (optional): Maximum results (default: 100)
- `offset` (optional): Results to skip (default: 0)

**Response:**
```json
[
  {
    "id": 1,
    "symbol": "AAPL",
    "name": "Apple Inc.",
    "type": "EQUITY",
    "currency": "USD",
    "created_at": "2023-12-01T10:00:00Z"
  }
]
```

### Get Instrument
```http
GET /api/instruments/{instrument_id}
```

### Create Instrument
```http
POST /api/instruments/
```

**Request Body:**
```json
{
  "symbol": "MSFT",
  "name": "Microsoft Corporation", 
  "type": "EQUITY",
  "currency": "USD"
}
```

**Valid Instrument Types:**
- `EQUITY` - Individual stocks
- `ETF` - Exchange-traded funds
- `MUTUAL_FUND` - Mutual funds
- `BOND` - Bonds and fixed income
- `CRYPTO` - Cryptocurrency
- `CASH` - Cash equivalents
- `OTHER` - Other instruments

### Update Instrument
```http
PUT /api/instruments/{instrument_id}
```

### Delete Instrument
```http
DELETE /api/instruments/{instrument_id}
```

---

## Transactions API

Manage investment transactions (trades, transfers, dividends, etc.).

### List Transactions
```http
GET /api/transactions/
```

**Query Parameters:**
- `account_id` (optional): Filter by account
- `instrument_id` (optional): Filter by instrument
- `type` (optional): Filter by transaction type
- `start_date` (optional): Filter by date (YYYY-MM-DD)
- `end_date` (optional): Filter by date (YYYY-MM-DD)
- `limit` (optional): Maximum results (default: 100)
- `offset` (optional): Results to skip (default: 0)

**Response:**
```json
[
  {
    "id": 1,
    "type": "TRADE",
    "date": "2023-12-01",
    "memo": "Buy 100 AAPL @ $150.00",
    "reference": "TXN-001",
    "status": "POSTED",
    "created_at": "2023-12-01T10:00:00Z",
    "lines": [
      {
        "id": 1,
        "account_id": 1,
        "account_name": "Assets:Brokerage",
        "instrument_id": 1,
        "instrument_symbol": "AAPL",
        "dr_cr": "DR",
        "amount": 15005.0,
        "quantity": 100.0
      },
      {
        "id": 2,
        "account_id": 2,
        "account_name": "Assets:Cash",
        "instrument_id": null,
        "instrument_symbol": null,
        "dr_cr": "CR",
        "amount": 15005.0,
        "quantity": null
      }
    ]
  }
]
```

### Get Transaction
```http
GET /api/transactions/{transaction_id}
```

### Create Transaction (Full Control)
```http
POST /api/transactions/
```

**Request Body:**
```json
{
  "type": "TRADE",
  "date": "2023-12-01", 
  "memo": "Buy 100 AAPL @ $150.00",
  "reference": "TXN-001",
  "lines": [
    {
      "account_id": 1,
      "instrument_id": 1,
      "dr_cr": "DR",
      "amount": 15005.0,
      "quantity": 100.0
    },
    {
      "account_id": 2,
      "dr_cr": "CR", 
      "amount": 15005.0
    }
  ]
}
```

**Valid Transaction Types:**
- `TRADE` - Buy/sell securities
- `TRANSFER` - Transfer between accounts
- `DIVIDEND` - Dividend payments
- `FEE` - Fees and commissions
- `TAX` - Tax payments
- `FX` - Foreign exchange
- `ADJUST` - Adjustments and corrections

### Create Trade (Simplified)
```http
POST /api/transactions/trade
```

**Request Body:**
```json
{
  "instrument_id": 1,
  "account_id": 1,
  "side": "BUY",
  "quantity": 100.0,
  "price": 150.0,
  "fees": 5.0,
  "date": "2023-12-01",
  "reference": "TXN-001"
}
```

**Valid Sides:**
- `BUY` - Purchase securities
- `SELL` - Sell securities

### Post Transaction
```http
POST /api/transactions/{transaction_id}/post
```
Make a draft transaction final and update lot tracking.

### Unpost Transaction
```http
POST /api/transactions/{transaction_id}/unpost
```
Revert a posted transaction back to draft status.

---

## Corporate Actions API

Manage corporate actions (splits, dividends, symbol changes).

### List Corporate Actions
```http
GET /api/corporate-actions/
```

**Query Parameters:**
- `instrument_id` (optional): Filter by instrument
- `type` (optional): Filter by action type
- `processed_only` (optional): Filter by processing status (true/false)
- `start_date` (optional): Filter by date (YYYY-MM-DD)
- `end_date` (optional): Filter by date (YYYY-MM-DD)
- `limit` (optional): Maximum results (default: 100)
- `offset` (optional): Results to skip (default: 0)

**Response:**
```json
[
  {
    "id": 1,
    "instrument_id": 1,
    "instrument_symbol": "AAPL",
    "instrument_name": "Apple Inc.",
    "type": "SPLIT",
    "date": "2023-12-01",
    "ratio": 2.0,
    "cash_per_share": null,
    "notes": "2:1 stock split",
    "processed": true,
    "created_at": "2023-12-01T10:00:00Z"
  }
]
```

### Get Corporate Action
```http
GET /api/corporate-actions/{action_id}
```

### Create Corporate Action
```http
POST /api/corporate-actions/
```

**Request Body:**
```json
{
  "instrument_id": 1,
  "type": "SPLIT",
  "date": "2023-12-01",
  "ratio": 2.0,
  "notes": "2:1 stock split",
  "auto_process": false
}
```

**Valid Action Types:**
- `SPLIT` - Stock split (requires `ratio`)
- `CASH_DIVIDEND` - Cash dividend (requires `cash_per_share`)
- `STOCK_DIVIDEND` - Stock dividend (requires `ratio`)
- `SYMBOL_CHANGE` - Symbol change
- `MERGER` - Merger event
- `SPINOFF` - Spinoff event

**Field Requirements by Type:**
- **SPLIT**: `ratio` (e.g., 2.0 for 2:1 split)
- **CASH_DIVIDEND**: `cash_per_share` (e.g., 0.25 for $0.25/share)
- **STOCK_DIVIDEND**: `ratio` (e.g., 0.05 for 5% stock dividend)

### Update Corporate Action
```http
PUT /api/corporate-actions/{action_id}
```
Only allowed for unprocessed actions.

### Process Corporate Action
```http
POST /api/corporate-actions/{action_id}/process
```

Apply the corporate action effects to positions and create accounting transactions.

**Response:**
```json
{
  "action_id": 1,
  "type": "SPLIT",
  "success": true,
  "message": "Corporate action processed successfully",
  "details": {
    "positions_affected": 1,
    "lots_modified": 2,
    "transactions_created": 1
  }
}
```

### Process Pending Actions
```http
POST /api/corporate-actions/process-pending
```

**Query Parameters:**
- `instrument_id` (optional): Process only for specific instrument

### Delete Corporate Action
```http
DELETE /api/corporate-actions/{action_id}
```
Only allowed for unprocessed actions.

### Get Summary Report
```http
GET /api/corporate-actions/summary/report
```

**Query Parameters:**
- `instrument_id` (optional): Filter by instrument
- `start_date` (optional): Filter by date (YYYY-MM-DD)
- `end_date` (optional): Filter by date (YYYY-MM-DD)

---

## Portfolio API

Portfolio-level analytics and position summaries.

### Get Portfolio Positions
```http
GET /api/portfolio/positions
```

**Query Parameters:**
- `account_id` (optional): Filter by account
- `instrument_id` (optional): Filter by instrument
- `include_pnl` (optional): Include P&L calculations (default: true)

**Response:**
```json
{
  "summary": {
    "total_cost_basis": 50000.0,
    "total_market_value": 55000.0,
    "total_unrealized_pnl": 5000.0,
    "total_pnl_percentage": 10.0,
    "position_count": 3,
    "valuation_date": "2023-12-01"
  },
  "positions": [
    {
      "instrument_id": 1,
      "instrument_symbol": "AAPL",
      "instrument_name": "Apple Inc.",
      "account_id": 1,
      "account_name": "Assets:Brokerage",
      "total_quantity": 200.0,
      "total_cost": 15000.0,
      "avg_cost_per_share": 75.0,
      "market_price": 155.0,
      "market_value": 31000.0,
      "unrealized_pnl": 16000.0,
      "pnl_percentage": 106.67,
      "lot_count": 2
    }
  ]
}
```

### Get Portfolio Summary
```http
GET /api/portfolio/summary
```

**Query Parameters:**
- `account_id` (optional): Filter by account

**Response:**
```json
{
  "total_cost_basis": 50000.0,
  "total_market_value": 55000.0,
  "total_unrealized_pnl": 5000.0,
  "total_pnl_percentage": 10.0,
  "position_count": 3,
  "valuation_date": "2023-12-01"
}
```

---

## Error Responses

All endpoints use a consistent error response format:

```json
{
  "ok": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message",
    "details": {
      "field": "Additional error context"
    }
  },
  "request_id": "unique-request-identifier"
}
```

**Common Error Codes:**
- `VALIDATION_ERROR` - Invalid request data
- `NOT_FOUND` - Resource not found
- `BUSINESS_LOGIC_ERROR` - Business rule violation
- `INTERNAL_SERVER_ERROR` - Server error

**Common HTTP Status Codes:**
- `200` - Success
- `400` - Bad Request (validation error)
- `404` - Not Found
- `500` - Internal Server Error

---

## Request Headers

**Content-Type:** `application/json` for POST/PUT requests

**Response Headers:**
- `X-Request-ID` - Unique identifier for request tracing
- `Content-Type` - `application/json`

---

## Development Notes

### Local Development
```bash
# Start the API server
cd backend
python main.py

# Server runs on http://localhost:8000
# API docs available at http://localhost:8000/docs (automatic)
```

### Database
- **Engine**: SQLite (local file: `backend/data/app.db`)
- **Migrations**: Alembic-based (in `backend/app/migrations/`)
- **Tables**: Auto-created on first startup

### CORS
Configured to allow requests from:
- `http://localhost:3000` (React dev server)
- `http://127.0.0.1:3000`

---

## Next Steps

1. **Frontend Integration**: Use these endpoints to build React components
2. **Price Data**: Add price endpoints for market data
3. **Reports**: Add specialized reporting endpoints
4. **Authentication**: Add user authentication if needed
5. **Bulk Operations**: Add batch endpoints for imports

For implementation examples and integration patterns, see the test files in `backend/tests/`.
