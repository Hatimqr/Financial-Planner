#!/bin/bash

# Frontend Integration Test Script
# Tests all the API endpoints that the frontend uses

set -e  # Exit on any error

BASE_URL="http://localhost:8000"
FRONTEND_ORIGIN="http://localhost:5174"

echo "🧪 Testing Frontend-Backend Integration"
echo "========================================"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test function
test_endpoint() {
    local name="$1"
    local url="$2"
    local expected_status="$3"
    
    echo -n "Testing $name... "
    
    response=$(curl -s -w "%{http_code}" \
        -H "Origin: $FRONTEND_ORIGIN" \
        -H "Accept: application/json, text/plain, */*" \
        -H "Referer: $FRONTEND_ORIGIN/" \
        "$url")
    
    status_code="${response: -3}"
    body="${response%???}"
    
    if [ "$status_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓ PASS${NC} (HTTP $status_code)"
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (HTTP $status_code, expected $expected_status)"
        return 1
    fi
}

# Test CORS headers specifically
test_cors() {
    local name="$1"
    local url="$2"
    
    echo -n "Testing CORS for $name... "
    
    cors_header=$(curl -s -I \
        -H "Origin: $FRONTEND_ORIGIN" \
        -H "Accept: application/json, text/plain, */*" \
        "$url" | grep -i "access-control-allow-origin" | tr -d '\r\n')
    
    if echo "$cors_header" | grep -q "$FRONTEND_ORIGIN"; then
        echo -e "${GREEN}✓ PASS${NC} (CORS enabled)"
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (CORS not configured properly)"
        echo "  Expected: access-control-allow-origin: $FRONTEND_ORIGIN"
        echo "  Got: $cors_header"
        return 1
    fi
}

# Test data structure
test_data_structure() {
    local name="$1"
    local url="$2"
    local required_field="$3"
    
    echo -n "Testing $name data structure... "
    
    response=$(curl -s \
        -H "Origin: $FRONTEND_ORIGIN" \
        -H "Accept: application/json, text/plain, */*" \
        "$url")
    
    if echo "$response" | jq -e ".$required_field" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASS${NC} (Contains $required_field)"
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (Missing $required_field)"
        echo "  Response: $(echo "$response" | head -c 200)..."
        return 1
    fi
}

# Start tests
echo -e "${YELLOW}Phase 1: Basic Connectivity${NC}"
echo "----------------------------"

# Test health endpoint
test_endpoint "Health Check" "$BASE_URL/health" "200" || exit 1

echo ""
echo -e "${YELLOW}Phase 2: CORS Configuration${NC}"
echo "----------------------------"

# Test CORS headers
test_cors "Accounts Endpoint" "$BASE_URL/api/accounts/" || exit 1
test_cors "Dashboard Summary" "$BASE_URL/api/dashboard/summary" || exit 1

echo ""
echo -e "${YELLOW}Phase 3: API Endpoints${NC}"
echo "----------------------------"

# Test all frontend endpoints
test_endpoint "Accounts List" "$BASE_URL/api/accounts/" "200" || exit 1
test_endpoint "Dashboard Summary" "$BASE_URL/api/dashboard/summary" "200" || exit 1
test_endpoint "Transactions List" "$BASE_URL/api/transactions/" "200" || exit 1

# Test timeseries with date parameters (YTD)
test_endpoint "Timeseries (YTD)" "$BASE_URL/api/dashboard/timeseries?start_date=2025-01-01&end_date=2025-08-16" "200" || exit 1

# Test account ledger (get first account ID dynamically)
ACCOUNT_ID=$(curl -s -H "Origin: $FRONTEND_ORIGIN" "$BASE_URL/api/accounts/" | jq -r '.[0].id' 2>/dev/null || echo "1")
test_endpoint "Account Ledger" "$BASE_URL/api/dashboard/accounts/$ACCOUNT_ID/ledger" "200" || exit 1

echo ""
echo -e "${YELLOW}Phase 4: Data Structure Validation${NC}"
echo "---------------------------------------"

# Test data structures match frontend expectations
echo -n "Testing Accounts data structure... "
ACCOUNTS_RESPONSE=$(curl -s -H "Origin: $FRONTEND_ORIGIN" "$BASE_URL/api/accounts/")
if echo "$ACCOUNTS_RESPONSE" | jq -e '.[0].id' > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PASS${NC} (Contains account id)"
else
    echo -e "${RED}✗ FAIL${NC} (Missing account id or empty array)"
fi

test_data_structure "Dashboard Summary" "$BASE_URL/api/dashboard/summary" "net_worth" || exit 1
test_data_structure "Dashboard Summary Accounts" "$BASE_URL/api/dashboard/summary" "account_balances" || exit 1
test_data_structure "Timeseries" "$BASE_URL/api/dashboard/timeseries?start_date=2025-08-01&end_date=2025-08-16" "data_points" || exit 1
test_data_structure "Timeseries Account Info" "$BASE_URL/api/dashboard/timeseries?start_date=2025-08-01&end_date=2025-08-16" "account_info" || exit 1

echo ""
echo -e "${YELLOW}Phase 5: Data Content Validation${NC}"
echo "-----------------------------------"

# Validate actual data content
echo -n "Testing account data presence... "
ACCOUNT_COUNT=$(curl -s -H "Origin: $FRONTEND_ORIGIN" "$BASE_URL/api/accounts/" | jq 'length' 2>/dev/null || echo "0")
if [ "$ACCOUNT_COUNT" -gt "0" ]; then
    echo -e "${GREEN}✓ PASS${NC} ($ACCOUNT_COUNT accounts found)"
else
    echo -e "${RED}✗ FAIL${NC} (No accounts found)"
    exit 1
fi

echo -n "Testing net worth calculation... "
NET_WORTH=$(curl -s -H "Origin: $FRONTEND_ORIGIN" "$BASE_URL/api/dashboard/summary" | jq '.net_worth' 2>/dev/null || echo "0")
if [ "$(echo "$NET_WORTH > 0" | bc 2>/dev/null)" = "1" ]; then
    echo -e "${GREEN}✓ PASS${NC} (Net worth: \$$NET_WORTH)"
else
    echo -e "${YELLOW}⚠ WARNING${NC} (Net worth: \$$NET_WORTH)"
fi

echo -n "Testing transaction data... "
TRANSACTION_COUNT=$(curl -s -H "Origin: $FRONTEND_ORIGIN" "$BASE_URL/api/transactions/" | jq 'length' 2>/dev/null || echo "0")
if [ "$TRANSACTION_COUNT" -gt "0" ]; then
    echo -e "${GREEN}✓ PASS${NC} ($TRANSACTION_COUNT transactions found)"
else
    echo -e "${YELLOW}⚠ WARNING${NC} (No transactions found)"
fi

echo ""
echo -e "${YELLOW}Phase 6: Frontend Simulation${NC}"
echo "-------------------------------"

# Simulate common frontend request patterns
echo -n "Testing dashboard page load sequence... "

# Simulate the exact sequence the Dashboard component makes
ACCOUNTS_RESPONSE=$(curl -s -H "Origin: $FRONTEND_ORIGIN" "$BASE_URL/api/accounts/")
SUMMARY_RESPONSE=$(curl -s -H "Origin: $FRONTEND_ORIGIN" "$BASE_URL/api/dashboard/summary")
TIMESERIES_RESPONSE=$(curl -s -H "Origin: $FRONTEND_ORIGIN" "$BASE_URL/api/dashboard/timeseries?start_date=2025-01-01&end_date=2025-08-16")

if [ -n "$ACCOUNTS_RESPONSE" ] && [ -n "$SUMMARY_RESPONSE" ] && [ -n "$TIMESERIES_RESPONSE" ]; then
    echo -e "${GREEN}✓ PASS${NC} (All dashboard data loaded)"
else
    echo -e "${RED}✗ FAIL${NC} (Dashboard data incomplete)"
    exit 1
fi

echo -n "Testing accounts page load sequence... "
if [ "$ACCOUNT_ID" != "null" ] && [ -n "$ACCOUNT_ID" ]; then
    LEDGER_RESPONSE=$(curl -s -H "Origin: $FRONTEND_ORIGIN" "$BASE_URL/api/dashboard/accounts/$ACCOUNT_ID/ledger")
    if [ -n "$LEDGER_RESPONSE" ]; then
        echo -e "${GREEN}✓ PASS${NC} (Account ledger loaded)"
    else
        echo -e "${RED}✗ FAIL${NC} (Account ledger failed)"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ SKIP${NC} (No account ID available)"
fi

echo ""
echo -e "${GREEN}🎉 All Frontend Integration Tests Passed!${NC}"
echo "============================================"
echo ""
echo "Summary:"
echo "- Backend API is responding correctly"
echo "- CORS is configured for frontend origin ($FRONTEND_ORIGIN)"
echo "- All data structures match frontend expectations"
echo "- Mock data is present and accessible"
echo "- Frontend should be able to load and display data properly"
echo ""
echo "Frontend URL: $FRONTEND_ORIGIN"
echo "Backend URL: $BASE_URL"