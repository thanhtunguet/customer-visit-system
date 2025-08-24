#!/usr/bin/env python3
"""
Debug script to test API startup issues
"""

import sys
import os
import logging
import traceback
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_imports():
    """Test all critical imports"""
    logger.info("Testing imports...")
    
    try:
        import fastapi
        logger.info("✓ FastAPI available")
    except ImportError as e:
        logger.error(f"✗ FastAPI import failed: {e}")
        return False
    
    try:
        import sqlalchemy
        logger.info("✓ SQLAlchemy available")
    except ImportError as e:
        logger.error(f"✗ SQLAlchemy import failed: {e}")
        return False
    
    try:
        from app.core.config import settings
        logger.info("✓ Config loaded successfully")
        logger.info(f"  Database URL: {settings.database_url}")
        logger.info(f"  Milvus: {settings.milvus_host}:{settings.milvus_port}")
        logger.info(f"  MinIO: {settings.minio_endpoint}")
    except Exception as e:
        logger.error(f"✗ Config import failed: {e}")
        return False
    
    try:
        from common.models import FaceDetectedEvent
        logger.info("✓ pkg_common.models available")
    except ImportError as e:
        logger.error(f"✗ pkg_common.models import failed: {e}")
        logger.error("Make sure packages/python/common is installed: pip install -e packages/python/common")
        return False
    
    return True

def test_database_connection():
    """Test database connectivity"""
    logger.info("Testing database connection...")
    
    try:
        from app.core.config import settings
        from sqlalchemy import create_engine, text
        
        # Create synchronous engine for testing
        engine = create_engine(settings.database_url.replace('+asyncpg', ''))
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info("✓ Database connection successful")
            return True
            
    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")
        logger.error("Check your .env file database configuration")
        return False

def test_external_services():
    """Test external service connections"""
    logger.info("Testing external services...")
    
    try:
        from app.core.milvus_client import milvus_client
        # Just test if the client can be created
        logger.info("✓ Milvus client created (mock or real)")
    except Exception as e:
        logger.error(f"✗ Milvus client failed: {e}")
    
    try:
        from app.core.minio_client import minio_client
        logger.info("✓ MinIO client created (mock or real)")
    except Exception as e:
        logger.error(f"✗ MinIO client failed: {e}")

def main():
    logger.info("=== API Startup Debug ===")
    
    # Test imports first
    if not test_imports():
        logger.error("Import tests failed. Cannot proceed.")
        return 1
    
    # Test database connection
    if not test_database_connection():
        logger.error("Database connection failed.")
        return 1
    
    # Test external services
    test_external_services()
    
    # Try to import the main app
    try:
        logger.info("Testing main app import...")
        from app.main import app
        logger.info("✓ Main app imported successfully")
        
        # Try to access the app info
        logger.info(f"App title: {app.title}")
        logger.info("✓ App appears to be properly configured")
        
    except Exception as e:
        logger.error(f"✗ Main app import/creation failed: {e}")
        traceback.print_exc()
        return 1
    
    logger.info("=== All tests passed! API should start normally ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())