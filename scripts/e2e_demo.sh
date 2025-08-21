#!/usr/bin/env bash
set -euo pipefail

# End-to-end demonstration script
echo "🚀 Customer Visits System E2E Demo"

# Function to check if service is healthy
check_service() {
    local url=$1
    local name=$2
    local max_attempts=30
    local attempt=1
    
    echo "⏳ Waiting for $name to be healthy..."
    while [ $attempt -le $max_attempts ]; do
        if curl -sf "$url" >/dev/null 2>&1; then
            echo "✅ $name is healthy"
            return 0
        fi
        echo "   Attempt $attempt/$max_attempts - waiting..."
        sleep 2
        ((attempt++))
    done
    
    echo "❌ $name failed to become healthy"
    return 1
}

# Start services with Docker Compose
echo "🔧 Starting services with Docker Compose..."
docker-compose -f infra/compose/docker-compose.dev.yml up -d --build

# Wait for services to be healthy
check_service "http://localhost:8080/v1/health" "API"

echo ""
echo "🎯 Running E2E Test Scenarios..."

# Test 1: API Health Check
echo "1. Testing API health endpoint..."
curl -sf http://localhost:8080/v1/health | jq '.' || echo "jq not available, raw response above"

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

TOKEN=$(echo $TOKEN_RESPONSE | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
echo "   Token obtained: ${TOKEN:0:20}..."

# Test 3: Create a site
echo "3. Creating a test site..."
curl -sf http://localhost:8080/v1/sites \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "site_id": "demo-site",
    "name": "Demo Site", 
    "location": "Test Location"
  }'

# Test 4: List sites
echo "4. Listing sites..."
curl -sf http://localhost:8080/v1/sites \
  -H "Authorization: Bearer $TOKEN"

# Test 5: Create staff member
echo "5. Creating staff member..."
EMBEDDING=$(python3 -c "import json; print(json.dumps([0.1] * 512))" 2>/dev/null || echo "[$(for i in {1..512}; do echo -n "0.1"; [ $i -lt 512 ] && echo -n ","; done)]")

curl -sf http://localhost:8080/v1/staff \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"staff_id\": \"staff-001\",
    \"name\": \"John Demo\",
    \"site_id\": \"demo-site\",
    \"face_embedding\": $EMBEDDING
  }"

# Test 6: Simulate face detection event
echo "6. Simulating face detection event..."
CUSTOMER_EMBEDDING=$(python3 -c "import json; print(json.dumps([0.2] * 512))" 2>/dev/null || echo "[$(for i in {1..512}; do echo -n "0.2"; [ $i -lt 512 ] && echo -n ","; done)]")

curl -sf http://localhost:8080/v1/events/face \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"tenant_id\": \"t-dev\",
    \"site_id\": \"demo-site\", 
    \"camera_id\": \"demo-cam\",
    \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
    \"embedding\": $CUSTOMER_EMBEDDING,
    \"bbox\": [10, 10, 100, 100],
    \"is_staff_local\": false
  }"

# Test 7: List visits
echo "7. Listing recent visits..."
curl -sf http://localhost:8080/v1/visits?limit=5 \
  -H "Authorization: Bearer $TOKEN"

# Test 8: Get visitor report
echo "8. Getting visitor report..."
WEEK_AGO=$(date -d '7 days ago' -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -v-7d -u +%Y-%m-%dT%H:%M:%SZ)
curl -sf "http://localhost:8080/v1/reports/visitors?granularity=day&start_date=$WEEK_AGO" \
  -H "Authorization: Bearer $TOKEN"

echo ""
echo "🎉 E2E Demo completed successfully!"
echo ""
echo "📊 Services are running:"
echo "   • API:      http://localhost:8080"  
echo "   • Web UI:   http://localhost:5173"
echo "   • MinIO:    http://localhost:9001 (minioadmin/minioadmin)"
echo ""
echo "💡 Next steps:"
echo "   • Open http://localhost:5173 in your browser"
echo "   • Login with: admin / password / t-dev / tenant_admin"
echo "   • Explore the dashboard and manage sites/staff/customers"
echo ""
echo "🛑 To stop all services:"
echo "   docker-compose -f infra/compose/docker-compose.dev.yml down"

