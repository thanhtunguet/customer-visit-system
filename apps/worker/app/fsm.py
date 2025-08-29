"""
Worker Finite State Machine (FSM) as per GPT Plan
States: INIT → REGISTERED → IDLE → RUNNING(camera_id) → RECONNECTING → DRAINING → STOPPED
"""
import asyncio
import logging
from enum import Enum
from typing import Optional, Dict, Any, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class WorkerState(Enum):
    """Worker FSM States as per GPT plan"""
    INIT = "INIT"
    REGISTERED = "REGISTERED" 
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    RECONNECTING = "RECONNECTING"
    DRAINING = "DRAINING"
    STOPPED = "STOPPED"


class FSMTransitionError(Exception):
    """Raised when invalid FSM transition is attempted"""
    pass


class WorkerFSM:
    """
    Worker Finite State Machine implementation
    
    Manages worker state transitions and validates allowed operations
    Based on GPT plan specifications
    """
    
    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self.state = WorkerState.INIT
        self.camera_id: Optional[str] = None
        self.last_transition = datetime.utcnow()
        self.transition_history: list = []
        
        # Event callbacks
        self.on_state_change: Optional[Callable] = None
        self.supervisor: Optional['PipelineSupervisor'] = None
        
        # Valid state transitions as per GPT plan
        self.valid_transitions = {
            WorkerState.INIT: [WorkerState.REGISTERED, WorkerState.STOPPED],
            WorkerState.REGISTERED: [WorkerState.IDLE, WorkerState.STOPPED, WorkerState.RECONNECTING],
            WorkerState.IDLE: [WorkerState.RUNNING, WorkerState.DRAINING, WorkerState.STOPPED, WorkerState.RECONNECTING],
            WorkerState.RUNNING: [WorkerState.IDLE, WorkerState.RECONNECTING, WorkerState.DRAINING, WorkerState.STOPPED],
            WorkerState.RECONNECTING: [WorkerState.REGISTERED, WorkerState.RUNNING, WorkerState.STOPPED],
            WorkerState.DRAINING: [WorkerState.STOPPED],
            WorkerState.STOPPED: []  # Terminal state
        }
        
        logger.info(f"WorkerFSM initialized for {worker_id} in state {self.state.value}")
    
    def transition_to(self, new_state: WorkerState, reason: Optional[str] = None) -> bool:
        """
        Transition to a new state with validation
        
        Args:
            new_state: Target state
            reason: Optional reason for transition
            
        Returns:
            True if transition successful, False otherwise
            
        Raises:
            FSMTransitionError: If transition is invalid
        """
        if new_state not in self.valid_transitions[self.state]:
            error_msg = f"Invalid transition from {self.state.value} to {new_state.value}"
            logger.error(f"FSM {self.worker_id}: {error_msg}")
            raise FSMTransitionError(error_msg)
        
        old_state = self.state
        self.state = new_state
        self.last_transition = datetime.utcnow()
        
        # Record transition history
        self.transition_history.append({
            "from": old_state.value,
            "to": new_state.value,
            "timestamp": self.last_transition,
            "reason": reason
        })
        
        logger.info(
            f"FSM {self.worker_id}: {old_state.value} → {new_state.value}" + 
            (f" (reason: {reason})" if reason else "")
        )
        
        # Trigger callback if set
        if self.on_state_change:
            try:
                self.on_state_change(self, old_state, new_state, reason)
            except Exception as e:
                logger.error(f"FSM {self.worker_id}: State change callback error: {e}")
        
        return True
    
    def can_transition_to(self, new_state: WorkerState) -> bool:
        """Check if transition to new state is valid"""
        return new_state in self.valid_transitions[self.state]
    
    def is_operational(self) -> bool:
        """Check if worker is in an operational state"""
        return self.state in [WorkerState.IDLE, WorkerState.RUNNING, WorkerState.RECONNECTING]
    
    def is_processing(self) -> bool:
        """Check if worker is actively processing"""
        return self.state == WorkerState.RUNNING
    
    def can_accept_camera(self) -> bool:
        """Check if worker can accept new camera assignment"""
        return self.state in [WorkerState.IDLE, WorkerState.RECONNECTING]
    
    def can_start_camera(self) -> bool:
        """Check if worker can start camera processing"""
        return self.state in [WorkerState.IDLE, WorkerState.RECONNECTING]
    
    # FSM Event Handlers (as per GPT plan)
    
    def on_register(self):
        """Handle worker registration"""
        if self.can_transition_to(WorkerState.REGISTERED):
            self.transition_to(WorkerState.REGISTERED, "worker_registered")
            return True
        return False
    
    def on_ready(self):
        """Handle worker ready (after registration)"""
        if self.can_transition_to(WorkerState.IDLE):
            self.transition_to(WorkerState.IDLE, "worker_ready")
            return True
        return False
    
    def on_start_camera(self, camera_id: str):
        """Handle START camera command"""
        if not self.can_start_camera():
            logger.warning(f"FSM {self.worker_id}: Cannot start camera in state {self.state.value}")
            return False
        
        self.camera_id = camera_id
        
        # Start pipeline via supervisor
        if self.supervisor:
            try:
                self.supervisor.start_pipeline(camera_id)
                self.transition_to(WorkerState.RUNNING, f"started_camera_{camera_id}")
                return True
            except Exception as e:
                logger.error(f"FSM {self.worker_id}: Failed to start pipeline: {e}")
                return False
        else:
            # Without supervisor, just transition state
            self.transition_to(WorkerState.RUNNING, f"started_camera_{camera_id}")
            return True
    
    def on_pipeline_ready(self):
        """Handle pipeline ready event"""
        if self.state == WorkerState.RUNNING:
            logger.info(f"FSM {self.worker_id}: Pipeline ready for camera {self.camera_id}")
            # Could emit pipeline_ready event here
            return True
        return False
    
    def on_stop_camera(self, reason: str = "requested"):
        """Handle STOP camera command"""
        if self.state == WorkerState.RUNNING:
            if self.supervisor:
                try:
                    self.supervisor.stop_pipeline()
                except Exception as e:
                    logger.error(f"FSM {self.worker_id}: Error stopping pipeline: {e}")
            
            self.camera_id = None
            self.transition_to(WorkerState.IDLE, f"stopped_camera_{reason}")
            return True
        return False
    
    def on_connection_error(self):
        """Handle connection/network errors"""
        if self.state in [WorkerState.RUNNING, WorkerState.IDLE, WorkerState.REGISTERED]:
            self.transition_to(WorkerState.RECONNECTING, "connection_error")
            return True
        return False
    
    def on_reconnected(self):
        """Handle successful reconnection"""
        if self.state == WorkerState.RECONNECTING:
            if self.camera_id:
                # Had camera assignment, go back to RUNNING
                self.transition_to(WorkerState.RUNNING, "reconnected_with_camera")
            else:
                # No camera, go to IDLE
                self.transition_to(WorkerState.IDLE, "reconnected_idle")
            return True
        return False
    
    def on_drain(self):
        """Handle DRAIN command (graceful shutdown)"""
        if self.can_transition_to(WorkerState.DRAINING):
            # Stop camera processing if running
            if self.state == WorkerState.RUNNING:
                self.on_stop_camera("draining")
            
            self.transition_to(WorkerState.DRAINING, "drain_requested")
            return True
        return False
    
    def on_shutdown(self, reason: str = "requested"):
        """Handle worker shutdown"""
        # Can transition to STOPPED from any state
        if self.state == WorkerState.RUNNING and self.supervisor:
            try:
                self.supervisor.stop_pipeline()
            except Exception as e:
                logger.error(f"FSM {self.worker_id}: Error during shutdown: {e}")
        
        self.camera_id = None
        self.transition_to(WorkerState.STOPPED, reason)
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Get current FSM status"""
        return {
            "worker_id": self.worker_id,
            "state": self.state.value,
            "camera_id": self.camera_id,
            "last_transition": self.last_transition.isoformat(),
            "is_operational": self.is_operational(),
            "is_processing": self.is_processing(),
            "can_accept_camera": self.can_accept_camera(),
            "transition_count": len(self.transition_history)
        }
    
    def get_transition_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent transition history"""
        return self.transition_history[-limit:]
    
    def set_supervisor(self, supervisor):
        """Set pipeline supervisor for camera operations"""
        self.supervisor = supervisor
        logger.info(f"FSM {self.worker_id}: Pipeline supervisor attached")
    
    def set_state_change_callback(self, callback: Callable):
        """Set callback for state change events"""
        self.on_state_change = callback


class PipelineSupervisor:
    """
    Placeholder for Pipeline Supervisor class
    Will be implemented as part of media pipeline hardening
    """
    
    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self.active_camera: Optional[str] = None
        
    def start_pipeline(self, camera_id: str):
        """Start camera pipeline"""
        logger.info(f"Pipeline {self.worker_id}: Starting pipeline for camera {camera_id}")
        self.active_camera = camera_id
        # TODO: Implement actual pipeline start logic
        
    def stop_pipeline(self):
        """Stop camera pipeline"""
        if self.active_camera:
            logger.info(f"Pipeline {self.worker_id}: Stopping pipeline for camera {self.active_camera}")
            self.active_camera = None
        # TODO: Implement actual pipeline stop logic