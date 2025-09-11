"""
Background Task Manager for preventing connection pool exhaustion and task leaks.

This module provides centralized task management to prevent the following issues:
1. Unhandled background tasks accumulating
2. Database connection pool exhaustion
3. Long-running tasks without proper cleanup
4. Task exceptions causing system instability
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, Optional, Set

logger = logging.getLogger(__name__)


class TaskManager:
    """Centralized task manager with connection pooling awareness."""

    def __init__(self, max_concurrent_tasks: int = 50, db_task_pool_size: int = 5):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.db_task_pool_size = db_task_pool_size

        # Task tracking
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.db_tasks: Set[asyncio.Task] = set()
        self.task_stats = {
            "total_created": 0,
            "total_completed": 0,
            "total_failed": 0,
            "active_count": 0,
            "db_tasks_count": 0,
        }

        # Thread pool for CPU-intensive tasks
        self.thread_pool = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="TaskManager"
        )

        # Cleanup task
        self.cleanup_task: Optional[asyncio.Task] = None
        self.cleanup_interval = 30  # seconds

    async def start(self):
        """Start the task manager and cleanup loop."""
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Task manager started")

    async def stop(self):
        """Stop the task manager and cleanup remaining tasks."""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass

        # Cancel all active tasks
        for task_id, task in self.active_tasks.items():
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled task: {task_id}")

        # Wait for tasks to complete with timeout
        if self.active_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.active_tasks.values(), return_exceptions=True),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                logger.warning("Some tasks did not complete within timeout")

        # Shutdown thread pool
        self.thread_pool.shutdown(wait=True)
        logger.info("Task manager stopped")

    def create_task(
        self,
        coro,
        name: Optional[str] = None,
        is_db_task: bool = False,
        timeout: Optional[float] = None,
    ) -> asyncio.Task:
        """
        Create a managed asyncio task with proper error handling.

        Args:
            coro: Coroutine to run
            name: Optional task name for tracking
            is_db_task: Whether this task uses database connections
            timeout: Optional timeout for the task

        Returns:
            asyncio.Task: The created task
        """
        if len(self.active_tasks) >= self.max_concurrent_tasks:
            raise RuntimeError(
                f"Too many concurrent tasks ({self.max_concurrent_tasks})"
            )

        if is_db_task and len(self.db_tasks) >= self.db_task_pool_size:
            raise RuntimeError(
                f"Too many concurrent DB tasks ({self.db_task_pool_size})"
            )

        task_id = name or f"task_{int(time.time() * 1000)}"

        # Wrap with timeout if specified
        if timeout:
            coro = asyncio.wait_for(coro, timeout=timeout)

        task = asyncio.create_task(coro, name=task_id)

        # Track the task
        self.active_tasks[task_id] = task
        if is_db_task:
            self.db_tasks.add(task)

        self.task_stats["total_created"] += 1
        self.task_stats["active_count"] = len(self.active_tasks)
        self.task_stats["db_tasks_count"] = len(self.db_tasks)

        # Add completion callback
        task.add_done_callback(
            lambda t: self._handle_task_completion(task_id, t, is_db_task)
        )

        logger.debug(f"Created {'DB ' if is_db_task else ''}task: {task_id}")
        return task

    def create_background_task(
        self,
        coro,
        name: Optional[str] = None,
        is_db_task: bool = False,
        timeout: Optional[float] = None,
    ):
        """
        Create a background task and return immediately (fire-and-forget).

        This is safer than raw asyncio.create_task() as it includes proper error handling.
        """
        try:
            return self.create_task(coro, name, is_db_task, timeout)
        except RuntimeError as e:
            logger.error(f"Failed to create background task {name}: {e}")
            return None

    async def run_in_thread(self, func: Callable, *args, **kwargs) -> Any:
        """Run a CPU-intensive function in a thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.thread_pool, func, *args, **kwargs)

    @asynccontextmanager
    async def db_task_semaphore(self):
        """Context manager to limit concurrent database tasks."""
        if len(self.db_tasks) >= self.db_task_pool_size:
            raise RuntimeError("DB task pool exhausted")
        try:
            yield
        finally:
            pass

    def _handle_task_completion(
        self, task_id: str, task: asyncio.Task, is_db_task: bool
    ):
        """Handle task completion and cleanup."""
        try:
            # Remove from tracking
            self.active_tasks.pop(task_id, None)
            if is_db_task:
                self.db_tasks.discard(task)

            # Update stats
            if task.exception():
                self.task_stats["total_failed"] += 1
                logger.error(f"Task {task_id} failed: {task.exception()}")
            else:
                self.task_stats["total_completed"] += 1
                logger.debug(f"Task {task_id} completed successfully")

            self.task_stats["active_count"] = len(self.active_tasks)
            self.task_stats["db_tasks_count"] = len(self.db_tasks)

        except Exception as e:
            logger.error(f"Error handling task completion for {task_id}: {e}")

    async def _cleanup_loop(self):
        """Background cleanup loop to remove completed tasks and log stats."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)

                # Clean up completed tasks
                completed_tasks = []
                for task_id, task in self.active_tasks.items():
                    if task.done():
                        completed_tasks.append(task_id)

                for task_id in completed_tasks:
                    self.active_tasks.pop(task_id, None)

                # Log stats if there are active tasks
                if self.active_tasks:
                    logger.info(
                        f"Task stats - Active: {len(self.active_tasks)}, "
                        f"DB: {len(self.db_tasks)}, "
                        f"Total created: {self.task_stats['total_created']}, "
                        f"Completed: {self.task_stats['total_completed']}, "
                        f"Failed: {self.task_stats['total_failed']}"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in task manager cleanup loop: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get current task manager statistics."""
        return {
            **self.task_stats,
            "active_count": len(self.active_tasks),
            "db_tasks_count": len(self.db_tasks),
            "active_task_names": list(self.active_tasks.keys()),
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "db_task_pool_size": self.db_task_pool_size,
        }


# Global task manager instance
task_manager = TaskManager()


# Convenience functions for common use cases
def create_task(
    coro, name: Optional[str] = None, timeout: Optional[float] = None
) -> Optional[asyncio.Task]:
    """Create a managed task (convenience function)."""
    return task_manager.create_background_task(
        coro, name, is_db_task=False, timeout=timeout
    )


def create_db_task(
    coro, name: Optional[str] = None, timeout: Optional[float] = 30.0
) -> Optional[asyncio.Task]:
    """Create a managed database task with default 30s timeout."""
    return task_manager.create_background_task(
        coro, name, is_db_task=True, timeout=timeout
    )


def create_broadcast_task(coro, name: Optional[str] = None) -> Optional[asyncio.Task]:
    """Create a managed broadcast task with 10s timeout."""
    return task_manager.create_background_task(
        coro, name, is_db_task=False, timeout=10.0
    )
