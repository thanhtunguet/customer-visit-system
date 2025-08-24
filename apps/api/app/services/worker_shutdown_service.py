"""
Worker shutdown service for graceful remote termination of workers.
This service manages shutdown signals and coordinates worker termination.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Set, Optional
from enum import Enum

from sqlalchemy import and_
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.database import Worker

logger = logging.getLogger(__name__)


class ShutdownSignal(str, Enum):
    """Types of shutdown signals"""
    GRACEFUL = "graceful"      # Normal shutdown, finish current work
    IMMEDIATE = "immediate"    # Stop immediately
    RESTART = "restart"        # Stop and restart


class WorkerShutdownService:
    """Service to manage worker shutdown signals and coordination"""
    
    def __init__(self):
        self.pending_shutdowns: Dict[str, dict] = {}  # worker_id -> shutdown_request
        self.shutdown_timeout = 30  # seconds to wait for graceful shutdown
        
    async def request_worker_shutdown(
        self, 
        worker_id: str, 
        signal: ShutdownSignal = ShutdownSignal.GRACEFUL,
        timeout: int = 30,
        requested_by: str = "system"
    ) -> dict:
        """
        Request a worker to shutdown gracefully
        
        Args:
            worker_id: Worker ID to shutdown
            signal: Type of shutdown signal
            timeout: Timeout in seconds for graceful shutdown
            requested_by: Who requested the shutdown
            
        Returns:
            dict: Shutdown request status
        """
        
        db = next(get_db())
        try:
            # Find the worker
            worker = db.query(Worker).filter(Worker.worker_id == worker_id).first()
            if not worker:
                return {"success": False, "error": "Worker not found"}
            
            # Create shutdown request
            shutdown_request = {
                "worker_id": worker_id,
                "worker_name": worker.worker_name,
                "hostname": worker.hostname,
                "signal": signal,
                "timeout": timeout,
                "requested_by": requested_by,
                "requested_at": datetime.utcnow(),
                "status": "pending"
            }
            
            # Store pending shutdown
            self.pending_shutdowns[worker_id] = shutdown_request
            
            # Update worker status to indicate shutdown requested
            worker.status = "shutting_down"
            worker.last_error = f"Shutdown requested by {requested_by}"
            worker.updated_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Shutdown requested for worker {worker_id} ({worker.worker_name}) by {requested_by}")
            
            # Start timeout monitoring
            asyncio.create_task(self._monitor_shutdown_timeout(worker_id, timeout))
            
            return {
                "success": True,
                "message": f"Shutdown requested for worker {worker.worker_name}",
                "shutdown_id": f"{worker_id}_{int(datetime.utcnow().timestamp())}",
                "timeout": timeout
            }
            
        except Exception as e:
            logger.error(f"Error requesting worker shutdown: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            db.close()
    
    async def get_shutdown_signal(self, worker_id: str) -> Optional[dict]:
        """
        Get pending shutdown signal for a worker (called by worker during heartbeat)
        
        Args:
            worker_id: Worker ID to check
            
        Returns:
            dict: Shutdown signal data or None
        """
        
        shutdown_request = self.pending_shutdowns.get(worker_id)
        if not shutdown_request:
            return None
        
        # Mark as delivered
        shutdown_request["status"] = "delivered"
        shutdown_request["delivered_at"] = datetime.utcnow()
        
        logger.info(f"Shutdown signal delivered to worker {worker_id}")
        
        return {
            "signal": shutdown_request["signal"],
            "timeout": shutdown_request["timeout"],
            "requested_by": shutdown_request["requested_by"],
            "message": f"Shutdown requested by {shutdown_request['requested_by']}"
        }
    
    async def acknowledge_shutdown(self, worker_id: str) -> bool:
        """
        Acknowledge that worker has received and is processing shutdown signal
        
        Args:
            worker_id: Worker ID acknowledging shutdown
            
        Returns:
            bool: Success status
        """
        
        if worker_id not in self.pending_shutdowns:
            return False
        
        shutdown_request = self.pending_shutdowns[worker_id]
        shutdown_request["status"] = "acknowledged"
        shutdown_request["acknowledged_at"] = datetime.utcnow()
        
        logger.info(f"Shutdown acknowledged by worker {worker_id}")
        return True
    
    async def complete_shutdown(self, worker_id: str) -> bool:
        """
        Mark worker shutdown as completed and cleanup
        
        Args:
            worker_id: Worker ID that completed shutdown
            
        Returns:
            bool: Success status
        """
        
        if worker_id not in self.pending_shutdowns:
            return False
        
        shutdown_request = self.pending_shutdowns[worker_id]
        shutdown_request["status"] = "completed"
        shutdown_request["completed_at"] = datetime.utcnow()
        
        # Remove from pending shutdowns after a delay (for logging)
        asyncio.create_task(self._cleanup_shutdown_request(worker_id, delay=60))
        
        # Update worker status in database
        db = next(get_db())
        try:
            worker = db.query(Worker).filter(Worker.worker_id == worker_id).first()
            if worker:
                worker.status = "offline"
                worker.camera_id = None  # Release camera
                worker.updated_at = datetime.utcnow()
                db.commit()
                
                # Broadcast worker update
                try:
                    from ..routers.workers import broadcast_worker_status_update
                    import asyncio
                    asyncio.create_task(broadcast_worker_status_update(worker, worker.tenant_id))
                except Exception as broadcast_error:
                    logger.error(f"Error broadcasting worker shutdown update: {broadcast_error}")
                
                logger.info(f"Worker {worker_id} shutdown completed gracefully")
        except Exception as e:
            logger.error(f"Error updating worker status after shutdown: {e}")
            db.rollback()
        finally:
            db.close()
        
        return True
    
    async def _monitor_shutdown_timeout(self, worker_id: str, timeout: int):
        """Monitor shutdown timeout and force cleanup if needed"""
        
        await asyncio.sleep(timeout)
        
        # Check if shutdown completed
        shutdown_request = self.pending_shutdowns.get(worker_id)
        if not shutdown_request or shutdown_request["status"] == "completed":
            return
        
        # Timeout occurred
        logger.warning(f"Worker {worker_id} shutdown timeout after {timeout}s")
        
        shutdown_request["status"] = "timeout"
        shutdown_request["timeout_at"] = datetime.utcnow()
        
        # Force worker offline status
        db = next(get_db())
        try:
            worker = db.query(Worker).filter(Worker.worker_id == worker_id).first()
            if worker:
                worker.status = "offline"
                worker.camera_id = None
                worker.last_error = f"Shutdown timeout after {timeout}s"
                worker.updated_at = datetime.utcnow()
                db.commit()
                
                # Broadcast worker update for timeout
                try:
                    from ..routers.workers import broadcast_worker_status_update
                    import asyncio
                    asyncio.create_task(broadcast_worker_status_update(worker, worker.tenant_id))
                except Exception as broadcast_error:
                    logger.error(f"Error broadcasting worker timeout update: {broadcast_error}")
                
                logger.warning(f"Forced worker {worker_id} offline due to shutdown timeout")
        except Exception as e:
            logger.error(f"Error forcing worker offline: {e}")
            db.rollback()
        finally:
            db.close()
        
        # Cleanup after delay
        await self._cleanup_shutdown_request(worker_id, delay=60)
    
    async def _cleanup_shutdown_request(self, worker_id: str, delay: int = 0):
        """Cleanup completed shutdown request"""
        if delay > 0:
            await asyncio.sleep(delay)
        
        self.pending_shutdowns.pop(worker_id, None)
        logger.debug(f"Cleaned up shutdown request for worker {worker_id}")
    
    def get_pending_shutdowns(self) -> Dict[str, dict]:
        """Get all pending shutdown requests"""
        return dict(self.pending_shutdowns)
    
    def get_shutdown_status(self, worker_id: str) -> Optional[dict]:
        """Get shutdown status for a specific worker"""
        return self.pending_shutdowns.get(worker_id)


# Global instance
worker_shutdown_service = WorkerShutdownService()