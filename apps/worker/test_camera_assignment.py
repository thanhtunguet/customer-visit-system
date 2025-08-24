#!/usr/bin/env python3
"""
Test script for multi-worker camera assignment system.
This script demonstrates the enhanced worker-backend architecture where:
1. Each worker reads SITE_ID from environment
2. Worker registers with backend providing only site_id
3. Backend automatically assigns available cameras to idle workers
4. Multiple workers can run against same site, each gets different camera
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from worker_client import WorkerClient
from main import WorkerConfig


class MockWorkerSimulator:
    """Simulates a worker for testing camera assignment"""
    
    def __init__(self, worker_name: str, env_file: str):
        self.worker_name = worker_name
        self.env_file = env_file
        self.config = None
        self.client = None
        self.running = False
    
    def load_config(self):
        """Load configuration from env file"""
        # Load environment variables from file
        if os.path.exists(self.env_file):
            with open(self.env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key] = value
        
        self.config = WorkerConfig()
        print(f"[{self.worker_name}] Loaded config - Site: {self.config.site_id}, Tenant: {self.config.tenant_id}")
    
    async def start(self):
        """Start the mock worker"""
        print(f"[{self.worker_name}] Starting worker simulation...")
        
        self.client = WorkerClient(self.config)
        await self.client.initialize()
        
        if self.client.worker_id:
            print(f"[{self.worker_name}] Worker registered with ID: {self.client.worker_id}")
            print(f"[{self.worker_name}] Assigned camera: {self.client.assigned_camera_id}")
            self.running = True
            
            # Simulate work loop
            await self.simulate_work()
        else:
            print(f"[{self.worker_name}] Failed to register worker")
    
    async def simulate_work(self):
        """Simulate worker processing faces"""
        work_cycles = 0
        
        while self.running and work_cycles < 10:  # Limit for demo
            try:
                # Check if we have a camera assigned
                if self.client.assigned_camera_id:
                    # Simulate processing
                    print(f"[{self.worker_name}] Processing faces on camera {self.client.assigned_camera_id}...")
                    await self.client.report_processing()
                    
                    # Simulate processing time
                    await asyncio.sleep(2)
                    
                    # Report faces processed
                    self.client.report_face_processed()
                    
                    # Back to idle
                    await self.client.report_idle()
                    print(f"[{self.worker_name}] Finished processing cycle {work_cycles + 1}")
                else:
                    # No camera assigned, request one
                    print(f"[{self.worker_name}] No camera assigned, requesting assignment...")
                    await self.client.request_camera_assignment()
                    await asyncio.sleep(1)
                
                work_cycles += 1
                await asyncio.sleep(3)  # Wait between cycles
                
            except Exception as e:
                print(f"[{self.worker_name}] Error in work loop: {e}")
                await asyncio.sleep(5)
                break
        
        print(f"[{self.worker_name}] Work simulation completed ({work_cycles} cycles)")
    
    async def stop(self):
        """Stop the worker"""
        print(f"[{self.worker_name}] Stopping worker...")
        self.running = False
        
        if self.client:
            await self.client.shutdown()
        
        print(f"[{self.worker_name}] Worker stopped")


async def test_multi_worker_assignment():
    """Test multiple workers with camera assignment"""
    
    print("=" * 60)
    print("Testing Multi-Worker Camera Assignment System")
    print("=" * 60)
    
    # Create multiple workers
    workers = [
        MockWorkerSimulator("WORKER-1", ".env.worker1"),
        MockWorkerSimulator("WORKER-2", ".env.worker2"),
        MockWorkerSimulator("WORKER-3", ".env.worker3"),
    ]
    
    # Load configurations
    for worker in workers:
        worker.load_config()
    
    print("\nStarting workers sequentially to observe assignment...")
    
    tasks = []
    try:
        # Start workers with delays to see assignment behavior
        for i, worker in enumerate(workers):
            print(f"\n--- Starting {worker.worker_name} ---")
            task = asyncio.create_task(worker.start())
            tasks.append(task)
            
            # Wait a bit between starting workers
            if i < len(workers) - 1:
                await asyncio.sleep(5)
        
        print("\nAll workers started. Let them run for a while...")
        
        # Let workers run for demo period
        await asyncio.sleep(30)
        
    except KeyboardInterrupt:
        print("\nReceived interrupt signal, stopping workers...")
    
    except Exception as e:
        print(f"Error during test: {e}")
    
    finally:
        # Stop all workers
        print("\n--- Stopping all workers ---")
        for worker in workers:
            await worker.stop()
        
        # Cancel any remaining tasks
        for task in tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        print("Test completed!")


if __name__ == "__main__":
    print("Multi-Worker Camera Assignment Test")
    print("Make sure the API server is running on http://localhost:8080")
    print("Press Ctrl+C to stop the test\n")
    
    try:
        asyncio.run(test_multi_worker_assignment())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test failed: {e}")