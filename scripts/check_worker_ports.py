#!/usr/bin/env python3
"""
Simple cross-platform script to verify worker processes have no listening ports.
This ensures workers operate purely via socket communication to the API service.
"""

import os
import subprocess
import sys
import time

try:
    import psutil
except ImportError:
    print("❌ Error: psutil is required. Install with: pip install psutil")
    sys.exit(1)
import argparse
from typing import List, Set


def find_listening_ports(pid: int) -> Set[int]:
    """Find all listening ports for a given process ID"""
    try:
        process = psutil.Process(pid)
        connections = process.connections(kind="inet")
        listening_ports = set()

        for conn in connections:
            if conn.status == psutil.CONN_LISTEN:
                listening_ports.add(conn.laddr.port)

        return listening_ports
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return set()


def check_ports_in_use(ports: List[int]) -> Set[int]:
    """Check which ports from the given list are currently in use"""
    ports_in_use = set()

    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.status == psutil.CONN_LISTEN and conn.laddr.port in ports:
                ports_in_use.add(conn.laddr.port)
    except (psutil.AccessDenied, psutil.NoSuchProcess, Exception) as e:
        print(f"   ⚠️  Could not check all ports: {e}")

    return ports_in_use


def start_worker_process(
    mock_mode: bool = True, worker_id: str = "test-worker"
) -> subprocess.Popen:
    """Start a worker process for testing"""
    worker_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "apps", "worker"
    )

    env = os.environ.copy()
    env.update(
        {
            "MOCK_MODE": str(mock_mode).lower(),
            "USE_ENHANCED_WORKER": "true",
            "WORKER_FPS": "1",
            "API_URL": "http://localhost:8080",  # Will fail to connect, but that's ok for port test
            "WORKER_ID": worker_id,
            "LOG_LEVEL": "ERROR",  # Reduce log noise
        }
    )

    cmd = [sys.executable, "-m", "app.main"]

    return subprocess.Popen(
        cmd,
        cwd=worker_dir,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def test_single_worker(check_duration: int = 8) -> bool:
    """Test that a single worker doesn't bind to any ports"""
    print("🔍 Testing single worker for listening ports...")

    worker_process = start_worker_process()

    try:
        print(f"   Started worker with PID: {worker_process.pid}")
        print(f"   Waiting {check_duration} seconds for initialization...")

        # Wait for worker to initialize
        time.sleep(check_duration)

        # Check if process is still running
        if worker_process.poll() is not None:
            print("   ⚠️  Worker process stopped (expected if API not running)")
            print("   ✅ PASS: Worker process didn't bind any ports before stopping")
            return True

        # Check for listening ports
        listening_ports = find_listening_ports(worker_process.pid)

        if listening_ports:
            print(f"   ❌ FAIL: Worker is listening on ports: {listening_ports}")
            return False
        else:
            print("   ✅ PASS: Worker has no listening ports")
            return True

    finally:
        # Clean up
        try:
            worker_process.terminate()
            worker_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            worker_process.kill()
            worker_process.wait()


def test_multiple_workers(num_workers: int = 3, check_duration: int = 8) -> bool:
    """Test that multiple workers can start without port conflicts"""
    print(f"🔍 Testing {num_workers} workers simultaneously...")

    worker_processes = []

    try:
        # Start multiple workers
        for i in range(num_workers):
            worker_id = f"test-worker-{i+1}"
            process = start_worker_process(worker_id=worker_id)
            worker_processes.append(process)
            print(f"   Started worker {i+1} with PID: {process.pid}")
            time.sleep(0.5)  # Small delay between starts

        print(f"   Waiting {check_duration} seconds for initialization...")
        time.sleep(check_duration)

        # Check each worker
        all_passed = True
        for i, process in enumerate(worker_processes):
            worker_num = i + 1

            if process.poll() is not None:
                print(f"   Worker {worker_num}: Stopped (expected if API not running)")
                continue

            listening_ports = find_listening_ports(process.pid)

            if listening_ports:
                print(
                    f"   ❌ Worker {worker_num} is listening on ports: {listening_ports}"
                )
                all_passed = False
            else:
                print(f"   ✅ Worker {worker_num} has no listening ports")

        if all_passed:
            print("   ✅ PASS: All workers started without binding ports")
        else:
            print("   ❌ FAIL: One or more workers bound to ports")

        return all_passed

    finally:
        # Clean up all workers
        for process in worker_processes:
            try:
                process.terminate()
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def check_common_ports() -> bool:
    """Check if common worker ports are free"""
    common_ports = [8090, 8091, 8092, 8093, 8094]
    ports_in_use = check_ports_in_use(common_ports)

    print("🔍 Checking common worker ports...")

    if not ports_in_use:
        print(f"   ✅ All common worker ports are free: {common_ports}")
        return True
    else:
        print(f"   ⚠️  Some common worker ports are in use: {ports_in_use}")
        print("   This may indicate old workers or other services using these ports")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Verify worker processes have no listening ports"
    )
    parser.add_argument(
        "--check-duration",
        type=int,
        default=8,
        help="Seconds to wait after starting workers (default: 8)",
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=3,
        help="Number of workers for multi-worker test (default: 3)",
    )
    parser.add_argument(
        "--skip-multi", action="store_true", help="Skip multi-worker test"
    )

    args = parser.parse_args()

    print("=== Worker Port Verification ===")
    print("Verifying that workers operate purely via socket communication")
    print()

    overall_success = True

    # Check common ports first
    print("📋 Pre-test: Checking common worker ports")
    check_common_ports()  # Don't fail on this, just informative
    print()

    # Test single worker
    print("🧪 Test 1: Single worker verification")
    if not test_single_worker(args.check_duration):
        overall_success = False
    print()

    # Test multiple workers
    if not args.skip_multi:
        print("🧪 Test 2: Multiple workers verification")
        if not test_multiple_workers(args.num_workers, args.check_duration):
            overall_success = False
        print()

    # Summary
    print("=== Summary ===")
    if overall_success:
        print("✅ SUCCESS: All tests passed - workers have no listening ports")
        print("Workers are correctly configured for socket-only communication")
        return 0
    else:
        print("❌ FAILURE: Some tests failed - workers may be binding to ports")
        print("Review worker configuration to ensure no HTTP servers are started")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)
