
# Financial Planner API Documentation - MVP

This document outlines the RESTful API endpoints for the Financial Planner MVP application.

**Base URL**: `http://localhost:8000/api`

---

## 🚀 MVP Core Endpoints

### **Accounts** - `/api/accounts`

All account management functionality is **✅ IMPLEMENTED**

#### `GET /api/accounts/`
Retrieves all financial accounts with optional filtering.

**Query Parameters:**
- `type` (optional): Filter by account type (ASSET, LIABILITY, EQUITY, INCOME, EXPENSE)
- `currency` (optional): Filter by currency

**Response:** Array of account objects with balance information

#### `POST /api/accounts/`
Creates a new financial account.

**Request Body:**
```json
{
  "name": "Chase Checking",
  "type": "ASSET",
  "currency": "USD"
}
```

#### `GET /api/accounts/{account_id}`
Retrieves a specific account by ID.

#### `PUT /api/accounts/{account_id}`
Updates an existing account's details.

**Request Body:**
```json
{
  "name": "Updated Account Name",
  "type": "ASSET"
}
```

#### `DELETE /api/accounts/{account_id}`
Deletes an account (only if no related transactions exist).

---

### **Transactions** - `/api/transactions`

Transaction management is **✅ IMPLEMENTED**

#### `GET /api/transactions/`
Retrieves transactions with filtering and pagination.

**Query Parameters:**
- `account_id` (optional): Filter by account
- `type` (optional): Filter by transaction type
- `start_date` (optional): Date filter (YYYY-MM-DD)
- `end_date` (optional): Date filter (YYYY-MM-DD)
- `limit` (optional): Max results (default: 100)
- `offset` (optional): Skip results (default: 0)

#### `POST /api/transactions/`
Creates a new double-entry transaction.

**Request Body:**
```json
{
  "type": "TRANSFER",
  "date": "2024-01-15",
  "memo": "Salary deposit",
  "lines": [
    {
      "account_id": 1,
      "dr_cr": "DR",
      "amount": 5000.00
    },
    {
      "account_id": 2,
      "dr_cr": "CR",
      "amount": 5000.00
    }
  ]
}
```

#### `POST /api/transactions/trade`
Simplified endpoint for creating trade transactions.

#### `GET /api/transactions/{transaction_id}`
Retrieves a specific transaction with all line details.

---

## 🎯 MVP Dashboard Endpoints ✅ IMPLEMENTED

All dashboard endpoints needed for the MVP are now implemented:

### **Dashboard Data** - `/api/dashboard`

#### `GET /api/dashboard/summary` ✅
**Purpose**: Powers the main dashboard summary cards

**Query Parameters:**
- `account_ids[]` (optional): Array of account IDs to include
- `as_of_date` (optional): Calculate as of specific date (default: today)

**Response:**
```json
{
  "net_worth": 125000.50,
  "total_assets": 150000.00,
  "total_liabilities": 25000.00,
  "total_equity": 0.00,
  "total_income": 75000.00,
  "total_expenses": 25000.00,
  "account_balances": [
    {
      "account_id": 1,
      "account_name": "Chase Checking",
      "account_type": "ASSET",
      "currency": "USD",
      "balance": 5000.00
    }
  ]
}
```

#### `GET /api/dashboard/timeseries` ✅
**Purpose**: Powers the main dashboard chart showing account balances over time

**Query Parameters:**
- `account_ids[]` (optional): Array of account IDs to include
- `start_date` (required): Start date (YYYY-MM-DD)
- `end_date` (required): End date (YYYY-MM-DD)
- `frequency` (optional): 'daily', 'weekly', 'monthly' (default: 'daily')

**Response:**
```json
{
  "data_points": [
    {
      "date": "2024-01-01",
      "accounts": {
        "1": 1000.00,
        "2": 2000.00
      },
      "net_worth": 3000.00
    }
  ],
  "account_info": {
    "1": {"name": "Chase Checking", "type": "ASSET"},
    "2": {"name": "Credit Card", "type": "LIABILITY"}
  }
}
```

#### `GET /api/dashboard/accounts/{account_id}/ledger` ✅
**Purpose**: Powers the T-account view showing debits and credits for a specific account

**Query Parameters:**
- `start_date` (optional): Filter transactions (YYYY-MM-DD)
- `end_date` (optional): Filter transactions (YYYY-MM-DD)
- `limit` (optional): Max results (default: 100, max: 1000)
- `offset` (optional): Pagination offset (default: 0)

**Response:**
```json
{
  "account": {
    "id": 1,
    "name": "Chase Checking",
    "type": "ASSET",
    "currency": "USD",
    "current_balance": 5000.00
  },
  "ledger_entries": [
    {
      "transaction_id": 1,
      "transaction_line_id": 1,
      "date": "2024-01-15",
      "memo": "Salary deposit",
      "transaction_type": "TRANSFER",
      "side": "DR",
      "amount": 5000.00,
      "running_balance": 5000.00
    }
  ],
  "total_entries": 1,
  "has_more": false
}
```

---

## 🔧 Implementation Status

**✅ Phase 1 Complete**: Core account and transaction management
- Full CRUD operations for accounts
- Double-entry transaction creation and management
- Transaction validation and posting system

**✅ Phase 2 Complete**: Dashboard endpoints for MVP frontend
- `GET /api/dashboard/summary` - Account balances and net worth calculation
- `GET /api/dashboard/timeseries` - Time series chart data with date filtering
- `GET /api/dashboard/accounts/{account_id}/ledger` - T-account ledger view with pagination

**🎯 MVP Backend Ready**: All required endpoints implemented for the MVP frontend

**Phase 3 (Future)**: Extended features beyond MVP scope
- Portfolio management and rebalancing
- Performance analytics and benchmarking  
- Import/export functionality
- Goal planning and simulations
