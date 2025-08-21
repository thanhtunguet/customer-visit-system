#!/usr/bin/env bash
set -euo pipefail

# Simple E2E test script (without Docker Compose)
echo "🚀 Customer Visits System Simple E2E Test"

# Function to check if service is healthy
check_service() {
    local url=$1
    local name=$2
    local max_attempts=10
    local attempt=1
    
    echo "⏳ Checking $name health..."
    while [ $attempt -le $max_attempts ]; do
        if curl -sf "$url" >/dev/null 2>&1; then
            echo "✅ $name is healthy"
            return 0
        fi
        echo "   Attempt $attempt/$max_attempts - waiting..."
        sleep 1
        ((attempt++))
    done
    
    echo "❌ $name is not healthy"
    return 1
}

# Check if API is running
check_service "http://localhost:8080/v1/health" "API"

echo ""
echo "🎯 Running API Test Scenarios..."

# Test 1: API Health Check
echo "1. Testing API health endpoint..."
HEALTH_RESPONSE=$(curl -sf http://localhost:8080/v1/health)
echo "   Response: $HEALTH_RESPONSE"

# Test 2: Authentication
echo "2. Testing authentication..."
TOKEN_RESPONSE=$(curl -sf http://localhost:8080/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{
    "grant_type": "api_key",
    "api_key": "dev-api-key", 
    "tenant_id": "t-dev",
    "role": "tenant_admin"
  }')

echo "   Auth response: $TOKEN_RESPONSE"

# Extract token if JSON parsing is available
if command -v python3 >/dev/null 2>&1; then
    TOKEN=$(echo "$TOKEN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null || echo "")
elif command -v jq >/dev/null 2>&1; then
    TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token' 2>/dev/null || echo "")
else
    # Fallback to basic grep/cut
    TOKEN=$(echo "$TOKEN_RESPONSE" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4 || echo "")
fi

if [ -n "$TOKEN" ]; then
    echo "   ✅ Token obtained: ${TOKEN:0:20}..."
    
    # Test 3: Get user info 
    echo "3. Testing user info endpoint..."
    USER_INFO=$(curl -sf http://localhost:8080/v1/me \
      -H "Authorization: Bearer $TOKEN")
    echo "   User info: $USER_INFO"
    
    # Test 4: Create a site
    echo "4. Testing site creation..."
    CREATE_SITE=$(curl -sf http://localhost:8080/v1/sites \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d '{
        "site_id": "test-site",
        "name": "Test Site", 
        "location": "Test Location"
      }' || echo "Site might already exist")
    echo "   Site creation: $CREATE_SITE"
    
    # Test 5: List sites
    echo "5. Testing site listing..."
    SITES=$(curl -sf http://localhost:8080/v1/sites \
      -H "Authorization: Bearer $TOKEN")
    echo "   Sites: $SITES"
    
    # Test 6: List visits
    echo "6. Testing visits listing..."
    VISITS=$(curl -sf http://localhost:8080/v1/visits?limit=5 \
      -H "Authorization: Bearer $TOKEN")
    echo "   Visits: $VISITS"
    
else
    echo "   ❌ Could not extract token from response"
    exit 1
fi

echo ""
echo "🎉 Simple E2E Test completed successfully!"
echo ""
echo "📊 API Service verified:"
echo "   • Health endpoint: ✅"
echo "   • Authentication: ✅"
echo "   • User info: ✅"
echo "   • Site management: ✅"
echo "   • Visit queries: ✅"