#!/bin/bash
#
# Script to verify worker has no listening ports
# This ensures workers operate purely via socket communication to API
#
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
WORKER_DIR="$PROJECT_ROOT/apps/worker"
CHECK_DURATION=10  # seconds to monitor after worker starts
EXPECTED_PORTS=(8090 8091 8092 8093 8094)  # Common worker ports to check

echo -e "${BLUE}=== Worker Port Verification Script ===${NC}"
echo "This script verifies that worker processes have no listening ports"
echo "Project root: $PROJECT_ROOT"
echo "Worker directory: $WORKER_DIR"
echo ""

# Function to check for listening ports
check_listening_ports() {
    local pid=$1
    local process_name=$2
    
    echo -e "${BLUE}Checking listening ports for PID $pid ($process_name)...${NC}"
    
    # Get all listening ports for this process
    local listening_ports
    if command -v lsof >/dev/null 2>&1; then
        listening_ports=$(lsof -Pan -p "$pid" -i 2>/dev/null | grep LISTEN || true)
    elif command -v netstat >/dev/null 2>&1; then
        listening_ports=$(netstat -tulnp 2>/dev/null | grep "$pid" | grep LISTEN || true)
    elif command -v ss >/dev/null 2>&1; then
        listening_ports=$(ss -tulnp 2>/dev/null | grep "pid=$pid" | grep LISTEN || true)
    else
        echo -e "${YELLOW}Warning: No suitable tool found to check ports (lsof, netstat, or ss)${NC}"
        return 1
    fi
    
    if [ -n "$listening_ports" ]; then
        echo -e "${RED}❌ FAIL: Worker process is listening on ports:${NC}"
        echo "$listening_ports"
        return 1
    else
        echo -e "${GREEN}✅ PASS: Worker process has no listening ports${NC}"
        return 0
    fi
}

# Function to check specific ports are not in use
check_specific_ports() {
    local ports_in_use=()
    
    echo -e "${BLUE}Checking if common worker ports are free...${NC}"
    
    for port in "${EXPECTED_PORTS[@]}"; do
        if command -v lsof >/dev/null 2>&1; then
            if lsof -i ":$port" >/dev/null 2>&1; then
                ports_in_use+=("$port")
            fi
        elif command -v netstat >/dev/null 2>&1; then
            if netstat -tuln 2>/dev/null | grep ":$port " >/dev/null; then
                ports_in_use+=("$port")
            fi
        elif command -v ss >/dev/null 2>&1; then
            if ss -tuln 2>/dev/null | grep ":$port " >/dev/null; then
                ports_in_use+=("$port")
            fi
        fi
    done
    
    if [ ${#ports_in_use[@]} -eq 0 ]; then
        echo -e "${GREEN}✅ PASS: No worker ports (${EXPECTED_PORTS[*]}) are in use${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  WARNING: Some worker ports are in use: ${ports_in_use[*]}${NC}"
        echo "This may indicate old workers still running or other services using these ports"
        return 1
    fi
}

# Function to start worker in background and monitor
test_worker_no_ports() {
    echo -e "${BLUE}Starting worker for port verification test...${NC}"
    
    # Change to worker directory
    cd "$WORKER_DIR"
    
    # Set environment for testing
    export MOCK_MODE=true
    export USE_ENHANCED_WORKER=true
    export WORKER_FPS=1  # Low FPS for testing
    export API_URL=http://localhost:8080  # Will fail to connect, but that's ok for port test
    
    # Start worker in background
    echo "Starting worker process..."
    python -m app.main > /tmp/worker_test.log 2>&1 &
    local worker_pid=$!
    
    echo "Worker started with PID: $worker_pid"
    echo "Waiting ${CHECK_DURATION} seconds for worker to initialize..."
    
    # Wait for worker to initialize
    sleep "$CHECK_DURATION"
    
    # Check if process is still running
    if ! kill -0 "$worker_pid" 2>/dev/null; then
        echo -e "${YELLOW}Worker process stopped. Checking logs...${NC}"
        echo "--- Worker logs ---"
        tail -20 /tmp/worker_test.log || echo "No logs available"
        echo "--- End logs ---"
        echo ""
        echo "This is expected if API is not running - the important thing is to verify no ports were bound"
    else
        echo "Worker process is running"
    fi
    
    # Check for listening ports (may have already stopped, that's ok)
    local ports_result=0
    if kill -0 "$worker_pid" 2>/dev/null; then
        check_listening_ports "$worker_pid" "worker" || ports_result=1
    else
        echo "Worker process has stopped - checking if any ports were bound during startup..."
        # Check the logs for any port binding messages
        if grep -i "listening\|bind\|port.*8090\|uvicorn\|fastapi" /tmp/worker_test.log 2>/dev/null; then
            echo -e "${RED}❌ FAIL: Worker logs show evidence of port binding${NC}"
            ports_result=1
        else
            echo -e "${GREEN}✅ PASS: No evidence of port binding in worker logs${NC}"
        fi
    fi
    
    # Clean up worker process
    if kill -0 "$worker_pid" 2>/dev/null; then
        echo "Stopping worker process..."
        kill -TERM "$worker_pid" 2>/dev/null || true
        sleep 2
        if kill -0 "$worker_pid" 2>/dev/null; then
            kill -KILL "$worker_pid" 2>/dev/null || true
        fi
    fi
    
    # Clean up log file
    rm -f /tmp/worker_test.log
    
    return $ports_result
}

# Function to run multiple worker test
test_multiple_workers() {
    echo -e "${BLUE}Testing multiple workers can start simultaneously...${NC}"
    
    cd "$WORKER_DIR"
    
    # Set environment for testing
    export MOCK_MODE=true
    export USE_ENHANCED_WORKER=true
    export WORKER_FPS=1
    export API_URL=http://localhost:8080
    
    local worker_pids=()
    local num_workers=3
    
    echo "Starting $num_workers workers simultaneously..."
    
    # Start multiple workers
    for i in $(seq 1 $num_workers); do
        export WORKER_ID="test-worker-$i"
        python -m app.main > "/tmp/worker_test_$i.log" 2>&1 &
        local pid=$!
        worker_pids+=("$pid")
        echo "Worker $i started with PID: $pid"
        sleep 0.5  # Small delay between starts
    done
    
    echo "Waiting for workers to initialize..."
    sleep "$CHECK_DURATION"
    
    # Check each worker for listening ports
    local overall_result=0
    for i in $(seq 0 $((num_workers-1))); do
        local pid=${worker_pids[$i]}
        local worker_num=$((i+1))
        
        echo -e "${BLUE}Checking worker $worker_num (PID: $pid)...${NC}"
        
        if kill -0 "$pid" 2>/dev/null; then
            check_listening_ports "$pid" "worker-$worker_num" || overall_result=1
        else
            echo "Worker $worker_num has stopped - checking logs for port binding..."
            if grep -i "listening\|bind\|port.*8090\|uvicorn\|fastapi" "/tmp/worker_test_$worker_num.log" 2>/dev/null; then
                echo -e "${RED}❌ FAIL: Worker $worker_num logs show evidence of port binding${NC}"
                overall_result=1
            else
                echo -e "${GREEN}✅ PASS: Worker $worker_num shows no evidence of port binding${NC}"
            fi
        fi
    done
    
    # Clean up all workers
    echo "Cleaning up test workers..."
    for pid in "${worker_pids[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done
    
    sleep 2
    
    # Force kill any remaining
    for pid in "${worker_pids[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill -KILL "$pid" 2>/dev/null || true
        fi
    done
    
    # Clean up log files
    for i in $(seq 1 $num_workers); do
        rm -f "/tmp/worker_test_$i.log"
    done
    
    if [ $overall_result -eq 0 ]; then
        echo -e "${GREEN}✅ PASS: All workers started without binding ports${NC}"
    else
        echo -e "${RED}❌ FAIL: One or more workers attempted to bind ports${NC}"
    fi
    
    return $overall_result
}

# Main execution
main() {
    local overall_result=0
    
    echo "=== Pre-test: Check for existing port usage ==="
    check_specific_ports || true  # Don't fail on this, just warn
    echo ""
    
    echo "=== Test 1: Single worker port verification ==="
    test_worker_no_ports || overall_result=1
    echo ""
    
    echo "=== Test 2: Multiple workers test ==="
    test_multiple_workers || overall_result=1
    echo ""
    
    echo -e "${BLUE}=== Summary ===${NC}"
    if [ $overall_result -eq 0 ]; then
        echo -e "${GREEN}✅ SUCCESS: All tests passed - workers have no listening ports${NC}"
        echo "Workers are correctly configured for socket-only communication"
    else
        echo -e "${RED}❌ FAILURE: Some tests failed - workers may be binding to ports${NC}"
        echo "Review worker configuration to ensure no HTTP servers are started"
    fi
    
    return $overall_result
}

# Run main function
main "$@"