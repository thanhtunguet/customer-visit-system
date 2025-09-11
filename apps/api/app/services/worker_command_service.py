from __future__ import annotations

import asyncio
import logging
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from common.enums.commands import CommandPriority, WorkerCommand

logger = logging.getLogger(__name__)


@dataclass
class WorkerCommandMessage:
    """Represents a command message for a worker"""

    command_id: str
    worker_id: str
    command: WorkerCommand
    parameters: Optional[Dict[str, Any]] = None
    priority: CommandPriority = CommandPriority.NORMAL
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    max_retries: int = 3
    retry_count: int = 0
    status: str = "pending"  # pending, sent, acknowledged, completed, failed, expired
    requested_by: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.expires_at is None:
            # Default expiry: 5 minutes for normal commands, 1 minute for urgent
            minutes = 1 if self.priority == CommandPriority.URGENT else 5
            self.expires_at = self.created_at + timedelta(minutes=minutes)

    def is_expired(self) -> bool:
        """Check if command has expired"""
        return datetime.utcnow() > self.expires_at

    def can_retry(self) -> bool:
        """Check if command can be retried"""
        return self.retry_count < self.max_retries and not self.is_expired()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "command_id": self.command_id,
            "worker_id": self.worker_id,
            "command": self.command.value,
            "parameters": self.parameters or {},
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "status": self.status,
            "requested_by": self.requested_by,
            "result": self.result,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }


class WorkerCommandService:
    """Service for managing worker commands"""

    def __init__(self):
        # Command queues per worker (priority queue)
        self.worker_queues: Dict[str, deque] = {}

        # Active commands being processed
        self.active_commands: Dict[str, WorkerCommandMessage] = {}

        # Command history (last 100 commands per worker)
        self.command_history: Dict[str, deque] = {}

        # Cleanup task
        self.cleanup_task: Optional[asyncio.Task] = None
        self.cleanup_interval = 60  # seconds

        # Callbacks for command events
        self.command_callbacks: List[callable] = []

    async def start(self):
        """Start the command service"""
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Worker command service started")

    async def stop(self):
        """Stop the command service"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            self.cleanup_task = None
            logger.info("Worker command service stopped")

    def add_command_callback(self, callback: Callable):
        """Add callback for command events"""
        self.command_callbacks.append(callback)

    async def _notify_callbacks(self, event_type: str, command: WorkerCommandMessage):
        """Notify all callbacks of command events"""
        for callback in self.command_callbacks:
            try:
                await callback(event_type, command)
            except Exception as e:
                logger.error(f"Error calling command callback: {e}")

    def send_command(
        self,
        worker_id: str,
        command: WorkerCommand,
        parameters: Optional[Dict[str, Any]] = None,
        priority: CommandPriority = CommandPriority.NORMAL,
        requested_by: Optional[str] = None,
        timeout_minutes: Optional[int] = None,
    ) -> str:
        """Send a command to a worker"""

        command_id = str(uuid.uuid4())

        # Create command message
        command_msg = WorkerCommandMessage(
            command_id=command_id,
            worker_id=worker_id,
            command=command,
            parameters=parameters,
            priority=priority,
            requested_by=requested_by,
        )

        # Set custom timeout if provided
        if timeout_minutes:
            command_msg.expires_at = command_msg.created_at + timedelta(
                minutes=timeout_minutes
            )

        # Add to worker queue (sorted by priority)
        if worker_id not in self.worker_queues:
            self.worker_queues[worker_id] = deque()

        # Insert based on priority (higher priority first)
        queue = self.worker_queues[worker_id]
        inserted = False
        for i, existing_cmd in enumerate(queue):
            if command_msg.priority.value > existing_cmd.priority.value:
                queue.insert(i, command_msg)
                inserted = True
                break

        if not inserted:
            queue.append(command_msg)

        # Add to active commands
        self.active_commands[command_id] = command_msg

        logger.info(
            f"Command {command.value} queued for worker {worker_id} with priority {priority.name}"
        )
        return command_id

    def get_pending_commands(
        self, worker_id: str, limit: int = 10
    ) -> List[WorkerCommandMessage]:
        """Get pending commands for a worker"""

        if worker_id not in self.worker_queues:
            return []

        queue = self.worker_queues[worker_id]
        commands = []

        # Get up to 'limit' commands from the front of the queue
        for i in range(min(limit, len(queue))):
            cmd = queue[i]
            if not cmd.is_expired():
                commands.append(cmd)
            else:
                # Mark expired commands
                cmd.status = "expired"

        return commands

    def acknowledge_command(self, command_id: str, worker_id: str) -> bool:
        """Acknowledge receipt of a command by worker"""

        command = self.active_commands.get(command_id)
        if not command or command.worker_id != worker_id:
            return False

        if command.is_expired():
            command.status = "expired"
            return False

        command.status = "acknowledged"
        logger.info(f"Command {command_id} acknowledged by worker {worker_id}")

        # Remove from worker queue
        if worker_id in self.worker_queues:
            queue = self.worker_queues[worker_id]
            self.worker_queues[worker_id] = deque(
                [cmd for cmd in queue if cmd.command_id != command_id]
            )

        return True

    def complete_command(
        self,
        command_id: str,
        worker_id: str,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """Mark command as completed by worker"""

        command = self.active_commands.get(command_id)
        if not command or command.worker_id != worker_id:
            return False

        if error_message:
            command.status = "failed"
            command.error_message = error_message
        else:
            command.status = "completed"
            command.result = result or {}

        # Move to history
        self._add_to_history(command)

        # Remove from active commands
        del self.active_commands[command_id]

        logger.info(f"Command {command_id} {command.status} by worker {worker_id}")
        return True

    def retry_command(self, command_id: str) -> bool:
        """Retry a failed command"""

        command = self.active_commands.get(command_id)
        if not command or not command.can_retry():
            return False

        command.retry_count += 1
        command.status = "pending"
        command.error_message = None

        # Add back to worker queue
        worker_id = command.worker_id
        if worker_id not in self.worker_queues:
            self.worker_queues[worker_id] = deque()

        # Insert at front for retry
        self.worker_queues[worker_id].appendleft(command)

        logger.info(
            f"Command {command_id} queued for retry (attempt {command.retry_count + 1})"
        )
        return True

    def get_command_status(self, command_id: str) -> Optional[WorkerCommandMessage]:
        """Get status of a specific command"""

        # Check active commands
        if command_id in self.active_commands:
            return self.active_commands[command_id]

        # Check history
        for worker_history in self.command_history.values():
            for cmd in worker_history:
                if cmd.command_id == command_id:
                    return cmd

        return None

    def get_worker_commands(
        self, worker_id: str, include_history: bool = False
    ) -> List[WorkerCommandMessage]:
        """Get all commands for a worker"""

        commands = []

        # Add pending commands
        commands.extend(self.get_pending_commands(worker_id))

        # Add active commands
        for cmd in self.active_commands.values():
            if cmd.worker_id == worker_id and cmd not in commands:
                commands.append(cmd)

        # Add history if requested
        if include_history and worker_id in self.command_history:
            commands.extend(list(self.command_history[worker_id]))

        # Sort by creation time (newest first)
        commands.sort(key=lambda x: x.created_at, reverse=True)
        return commands

    def cancel_command(
        self, command_id: str, reason: str = "Cancelled by admin"
    ) -> bool:
        """Cancel a pending or active command"""

        command = self.active_commands.get(command_id)
        if not command:
            return False

        command.status = "cancelled"
        command.error_message = reason

        # Remove from worker queue
        worker_id = command.worker_id
        if worker_id in self.worker_queues:
            queue = self.worker_queues[worker_id]
            self.worker_queues[worker_id] = deque(
                [cmd for cmd in queue if cmd.command_id != command_id]
            )

        # Move to history
        self._add_to_history(command)

        # Remove from active commands
        del self.active_commands[command_id]

        logger.info(f"Command {command_id} cancelled: {reason}")
        return True

    def _add_to_history(self, command: WorkerCommandMessage):
        """Add command to history"""

        worker_id = command.worker_id
        if worker_id not in self.command_history:
            self.command_history[worker_id] = deque(maxlen=100)

        self.command_history[worker_id].appendleft(command)

    async def _cleanup_loop(self):
        """Background cleanup task"""

        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired_commands()
            except asyncio.CancelledError:
                logger.info("Command service cleanup loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in command service cleanup loop: {e}")

    async def _cleanup_expired_commands(self):
        """Clean up expired commands"""

        expired_count = 0

        # Check active commands
        expired_commands = []
        for command_id, command in self.active_commands.items():
            if command.is_expired():
                expired_commands.append(command_id)

        # Mark as expired and move to history
        for command_id in expired_commands:
            command = self.active_commands[command_id]
            command.status = "expired"

            # Remove from worker queue
            worker_id = command.worker_id
            if worker_id in self.worker_queues:
                queue = self.worker_queues[worker_id]
                self.worker_queues[worker_id] = deque(
                    [cmd for cmd in queue if cmd.command_id != command_id]
                )

            # Move to history
            self._add_to_history(command)

            # Remove from active commands
            del self.active_commands[command_id]
            expired_count += 1

        if expired_count > 0:
            logger.info(f"Cleaned up {expired_count} expired commands")

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics"""

        total_active = len(self.active_commands)
        total_pending = sum(len(queue) for queue in self.worker_queues.values())
        total_history = sum(len(history) for history in self.command_history.values())

        # Status breakdown
        status_counts: Dict[str, int] = {}
        for command in self.active_commands.values():
            status_counts[command.status] = status_counts.get(command.status, 0) + 1

        return {
            "total_active_commands": total_active,
            "total_pending_commands": total_pending,
            "total_historical_commands": total_history,
            "active_workers": len(self.worker_queues),
            "status_breakdown": status_counts,
        }


# Global worker command service
worker_command_service = WorkerCommandService()
