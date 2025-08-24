#!/usr/bin/env python3
"""Test worker registration and authentication"""
import os
import asyncio

# Set environment variables
os.environ['API_URL'] = 'http://localhost:8080'
os.environ['WORKER_API_KEY'] = 'dev-secret'
os.environ['TENANT_ID'] = 't-dev'
os.environ['SITE_ID'] = 's-1'  
os.environ['CAMERA_ID'] = 'c-1'

from app.main import WorkerConfig
from app.worker_client import WorkerClient

async def test_worker_registration():
    """Test worker authentication and registration"""
    print('Testing worker authentication with updated configuration...')
    
    config = WorkerConfig()
    print(f'API URL: {config.api_url}')
    print(f'API Key configured: {bool(config.worker_api_key and config.worker_api_key != "dev-api-key")}')
    print(f'Tenant ID: {config.tenant_id}')
    print(f'Site ID: {config.site_id}')
    print(f'Camera ID: {config.camera_id}')
    
    client = WorkerClient(config)
    
    try:
        await client.initialize()
        print('Worker client initialized successfully')
        
        result = await client.register()
        print(f'Registration successful: {result}')
        
        # Test heartbeat
        if client.worker_id:
            heartbeat_result = await client.send_heartbeat()
            print(f'Heartbeat successful: {heartbeat_result}')
        
    except Exception as e:
        print(f'Registration failed: {e}')
        import traceback
        traceback.print_exc()
    
    finally:
        await client.shutdown()

if __name__ == "__main__":
    asyncio.run(test_worker_registration())