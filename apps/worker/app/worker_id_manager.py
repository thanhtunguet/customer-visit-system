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
        Get worker ID with fallback chain:
        1. Environment variable WORKER_ID
        2. .env file WORKER_ID 
        3. Existing persistent storage (only if no env/dotenv WORKER_ID)
        4. Auto-generate new UUID
        
        When WORKER_ID is set via env var or .env file, it bypasses persistent storage
        to avoid collisions between multiple workers.
        """
        try:
            # 1. Check environment variable first (highest priority)
            env_worker_id = os.getenv("WORKER_ID")
            if env_worker_id and env_worker_id.strip():
                worker_id = env_worker_id.strip()
                logger.info(f"Using WORKER_ID from environment variable: {worker_id}")
                # Don't save to persistent storage to avoid collision with other workers
                return worker_id
            
            # 2. Check .env file if no environment variable (second priority)
            dotenv_worker_id = self._load_from_dotenv()
            if dotenv_worker_id and dotenv_worker_id.strip():
                worker_id = dotenv_worker_id.strip()
                logger.info(f"Using WORKER_ID from .env file: {worker_id}")
                # Save to worker-specific storage to avoid collisions
                self._save_worker_id(worker_id, tenant_id, site_id, worker_id_suffix=worker_id)
                return worker_id
            
            # 3. Try to load existing worker ID from persistent storage (third priority)
            # Only use default storage when no explicit WORKER_ID is set
            existing_id = self._load_worker_id(tenant_id, site_id)
            if existing_id:
                logger.info(f"Loaded existing worker ID from persistent storage: {existing_id}")
                return existing_id
            
            # 4. Create new worker ID as fallback (lowest priority)
            new_id = self._generate_worker_id()
            self._save_worker_id(new_id, tenant_id, site_id)
            logger.info(f"Auto-generated new worker ID: {new_id}")
            return new_id
            
        except Exception as e:
            logger.error(f"Error managing worker ID: {e}")
            # Fallback to generating a new ID
            return self._generate_worker_id()
    
    def _get_worker_id_file(self, tenant_id: str, worker_id_suffix: Optional[str] = None) -> Path:
        """Get the worker ID file path for a specific tenant and optional worker ID"""
        # Use tenant-specific filename to avoid conflicts
        safe_tenant_id = tenant_id.replace('/', '_').replace('\\', '_')
        
        if worker_id_suffix:
            # Use worker-specific filename when WORKER_ID is explicitly set
            safe_worker_suffix = worker_id_suffix.replace('/', '_').replace('\\', '_').replace(':', '_')
            return self.data_dir / f"worker_id_{safe_tenant_id}_{safe_worker_suffix}.json"
        else:
            # Use default filename for auto-generated worker IDs
            return self.data_dir / f"worker_id_{safe_tenant_id}.json"

    
    def _load_from_dotenv(self) -> Optional[str]:
        """Load WORKER_ID from .env file in the worker directory"""
        try:
            # Look for .env file in multiple locations, prioritizing current working directory for flexibility
            current_dir = Path(__file__).parent
            env_file_paths = [
                Path.cwd() / ".env",                # current working directory (for testing)
                current_dir.parent / ".env",        # apps/worker/.env (main location)
                current_dir / ".env",               # apps/worker/app/.env
                current_dir.parent.parent / ".env", # apps/.env
            ]
            
            for env_file in env_file_paths:
                if env_file.exists():
                    logger.debug(f"Checking .env file: {env_file}")
                    try:
                        with open(env_file, 'r') as f:
                            for line in f:
                                line = line.strip()
                                if line.startswith('WORKER_ID=') and not line.startswith('#'):
                                    worker_id = line.split('=', 1)[1].strip()
                                    # Remove quotes if present
                                    if (worker_id.startswith('"') and worker_id.endswith('"')) or \
                                       (worker_id.startswith("'") and worker_id.endswith("'")):
                                        worker_id = worker_id[1:-1]
                                    if worker_id:
                                        logger.debug(f"Found WORKER_ID in {env_file}: {worker_id}")
                                        return worker_id
                    except (OSError, IOError) as e:
                        logger.debug(f"Could not read .env file {env_file}: {e}")
                        continue
            
            logger.debug("No WORKER_ID found in .env files")
            return None
            
        except Exception as e:
            logger.debug(f"Error loading from .env file: {e}")
            return None
    
    def _load_worker_id(self, tenant_id: str, site_id: Optional[str] = None, worker_id_suffix: Optional[str] = None) -> Optional[str]:
        """Load worker ID from persistent storage"""
        worker_id_file = self._get_worker_id_file(tenant_id, worker_id_suffix)
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
    
    def _save_worker_id(self, worker_id: str, tenant_id: str, site_id: Optional[str] = None, worker_id_suffix: Optional[str] = None):
        """Save worker ID to persistent storage"""
        worker_id_file = self._get_worker_id_file(tenant_id, worker_id_suffix)
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
        # Try to find the worker ID file - check both worker-specific and default locations
        worker_id_files = []
        
        # Add worker-specific file if worker_id looks like it was explicitly set
        if not worker_id.startswith('worker-') or len(worker_id.split('-')) > 2:
            worker_id_files.append(self._get_worker_id_file(tenant_id, worker_id))
        
        # Add default file location
        worker_id_files.append(self._get_worker_id_file(tenant_id))
        
        for worker_id_file in worker_id_files:
            try:
                if not worker_id_file.exists():
                    continue
                
                with open(worker_id_file, 'r') as f:
                    data = json.load(f)
                
                # Update only if the worker ID matches
                if data.get('worker_id') == worker_id:
                    data['last_used'] = str(self._get_current_timestamp())
                    
                    with open(worker_id_file, 'w') as f:
                        json.dump(data, f, indent=2)
                    
                    logger.debug(f"Updated last used timestamp for worker ID {worker_id}")
                    return  # Successfully updated, exit
                
            except (json.JSONDecodeError, OSError) as e:
                logger.debug(f"Failed to update last used timestamp in {worker_id_file}: {e}")
                continue
    
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
        """Generate a new unique worker ID with readable format"""
        # Generate UUID but use a more readable format
        unique_id = str(uuid.uuid4())[:8]  # Use first 8 characters of UUID
        return f"worker-{unique_id}"
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp as ISO string"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


# Global instance for easy access
worker_id_manager = WorkerIDManager()