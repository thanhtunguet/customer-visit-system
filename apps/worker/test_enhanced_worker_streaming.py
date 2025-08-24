#!/usr/bin/env python3
"""
Test script for enhanced worker with streaming capabilities
"""
import asyncio
import os
import sys
import logging

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.enhanced_worker_with_streaming import run_enhanced_worker

# Configure logging for testing
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if __name__ == "__main__":
    print("Starting enhanced worker with streaming test...")
    print("Press Ctrl+C to stop")
    
    try:
        asyncio.run(run_enhanced_worker())
    except KeyboardInterrupt:
        print("\nTest stopped by user")
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)