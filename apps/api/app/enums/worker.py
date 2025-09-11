from enum import Enum


class WorkerStatus(Enum):
    """Worker status enumeration"""

    IDLE = "idle"
    PROCESSING = "processing"
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    MAINTENANCE = "maintenance"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_string(cls, status: str) -> "WorkerStatus":
        """Create WorkerStatus from string value"""
        for worker_status in cls:
            if worker_status.value == status.lower():
                return worker_status
        raise ValueError(f"Invalid worker status: {status}")

    @classmethod
    def get_active_statuses(cls) -> list["WorkerStatus"]:
        """Get list of statuses considered as 'active'"""
        return [cls.IDLE, cls.PROCESSING, cls.ONLINE]

    @classmethod
    def get_inactive_statuses(cls) -> list["WorkerStatus"]:
        """Get list of statuses considered as 'inactive'"""
        return [cls.OFFLINE, cls.ERROR, cls.MAINTENANCE]

    def is_active(self) -> bool:
        """Check if this status is considered active"""
        return self in self.get_active_statuses()

    def is_inactive(self) -> bool:
        """Check if this status is considered inactive"""
        return self in self.get_inactive_statuses()
