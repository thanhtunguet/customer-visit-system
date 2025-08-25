"""
Worker ID Manager - Handles persistent worker ID storage
Similar to PID file mechanism, maintains worker identity across restarts
"""
import json
import logging
import os
import socket
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class WorkerIDManager:
    """Manages persistent worker ID storage and retrieval"""
    
    def __init__(self, data_dir: str = ".worker_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.hostname = socket.gethostname()
    
    def get_or_create_worker_id(self, tenant_id: str, site_id: Optional[str] = None) -> str:
        """
        Get existing worker ID or create a new one.
        Worker ID is tied to hostname and tenant for uniqueness.
        Each tenant gets its own worker ID file to avoid conflicts.
        """
        try:
            # Try to load existing worker ID for this specific tenant/site combination
            existing_id = self._load_worker_id(tenant_id, site_id)
            if existing_id:
                logger.info(f"Loaded existing worker ID: {existing_id}")
                return existing_id
            
            # Create new worker ID for this tenant/site combination
            new_id = self._generate_worker_id()
            self._save_worker_id(new_id, tenant_id, site_id)
            logger.info(f"Created new worker ID: {new_id}")
            return new_id
            
        except Exception as e:
            logger.error(f"Error managing worker ID: {e}")
            # Fallback to generating a new ID
            return self._generate_worker_id()
    
    def _get_worker_id_file(self, tenant_id: str) -> Path:
        """Get the worker ID file path for a specific tenant"""
        # Use tenant-specific filename to avoid conflicts
        safe_tenant_id = tenant_id.replace('/', '_').replace('\\', '_')
        return self.data_dir / f"worker_id_{safe_tenant_id}.json"
    
    def _load_worker_id(self, tenant_id: str, site_id: Optional[str] = None) -> Optional[str]:
        """Load worker ID from persistent storage"""
        worker_id_file = self._get_worker_id_file(tenant_id)
        if not worker_id_file.exists():
            return None
        
        try:
            with open(worker_id_file, 'r') as f:
                data = json.load(f)
            
            # Validate the stored data matches current context
            if (data.get('hostname') == self.hostname and 
                data.get('tenant_id') == tenant_id):
                
                # Optional site_id validation (if specified)
                stored_site_id = data.get('site_id')
                if site_id is None or stored_site_id is None or stored_site_id == site_id:
                    worker_id = data.get('worker_id')
                    if worker_id:
                        logger.debug(f"Found valid worker ID for hostname={self.hostname}, tenant={tenant_id}")
                        return worker_id
            
            logger.info(f"Stored worker ID doesn't match current context (hostname={self.hostname}, tenant={tenant_id})")
            return None
            
        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.warning(f"Failed to load worker ID file: {e}")
            return None
    
    def _save_worker_id(self, worker_id: str, tenant_id: str, site_id: Optional[str] = None):
        """Save worker ID to persistent storage"""
        worker_id_file = self._get_worker_id_file(tenant_id)
        try:
            data = {
                'worker_id': worker_id,
                'hostname': self.hostname,
                'tenant_id': tenant_id,
                'site_id': site_id,
                'created_at': str(self._get_current_timestamp()),
                'last_used': str(self._get_current_timestamp())
            }
            
            with open(worker_id_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"Saved worker ID {worker_id} to {worker_id_file}")
            
        except OSError as e:
            logger.error(f"Failed to save worker ID file: {e}")
    
    def update_last_used(self, worker_id: str, tenant_id: str, site_id: Optional[str] = None):
        """Update the last used timestamp for the worker ID"""
        worker_id_file = self._get_worker_id_file(tenant_id)
        try:
            if not worker_id_file.exists():
                return
            
            with open(worker_id_file, 'r') as f:
                data = json.load(f)
            
            # Update only if the worker ID matches
            if data.get('worker_id') == worker_id:
                data['last_used'] = str(self._get_current_timestamp())
                
                with open(worker_id_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                logger.debug(f"Updated last used timestamp for worker ID {worker_id}")
            
        except (json.JSONDecodeError, OSError) as e:
            logger.debug(f"Failed to update last used timestamp: {e}")
    
    def clear_worker_id(self, tenant_id: Optional[str] = None):
        """Clear the stored worker ID (for cleanup or reset)"""
        try:
            if tenant_id:
                # Clear specific tenant's worker ID
                worker_id_file = self._get_worker_id_file(tenant_id)
                if worker_id_file.exists():
                    worker_id_file.unlink()
                    logger.info(f"Cleared stored worker ID for tenant {tenant_id}")
            else:
                # Clear all worker ID files
                for file in self.data_dir.glob("worker_id_*.json"):
                    file.unlink()
                    logger.info(f"Cleared worker ID file: {file}")
        except OSError as e:
            logger.warning(f"Failed to clear worker ID file: {e}")
    
    def get_worker_info(self, tenant_id: str) -> Optional[dict]:
        """Get stored worker information for a specific tenant"""
        worker_id_file = self._get_worker_id_file(tenant_id)
        try:
            if not worker_id_file.exists():
                return None
            
            with open(worker_id_file, 'r') as f:
                return json.load(f)
                
        except (json.JSONDecodeError, OSError):
            return None
    
    def _generate_worker_id(self) -> str:
        """Generate a new unique worker ID"""
        return str(uuid.uuid4())
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp as ISO string"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


# Global instance for easy access
worker_id_manager = WorkerIDManager()