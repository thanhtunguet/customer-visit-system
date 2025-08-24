from enum import Enum


class WorkerCommand(Enum):
    """Worker command enumeration"""
    START_PROCESSING = "start_processing"
    STOP_PROCESSING = "stop_processing"
    START_STREAMING = "start_streaming" 
    STOP_STREAMING = "stop_streaming"
    RESTART = "restart"
    STATUS_REPORT = "status_report"
    ASSIGN_CAMERA = "assign_camera"
    RELEASE_CAMERA = "release_camera"
    SHUTDOWN = "shutdown"
    
    def __str__(self) -> str:
        return self.value
    
    @classmethod
    def from_string(cls, command: str) -> 'WorkerCommand':
        """Create WorkerCommand from string value"""
        for worker_command in cls:
            if worker_command.value == command.lower():
                return worker_command
        raise ValueError(f"Invalid worker command: {command}")
    
    @classmethod
    def get_processing_commands(cls) -> list['WorkerCommand']:
        """Get commands related to processing"""
        return [cls.START_PROCESSING, cls.STOP_PROCESSING]
    
    @classmethod
    def get_streaming_commands(cls) -> list['WorkerCommand']:
        """Get commands related to streaming"""
        return [cls.START_STREAMING, cls.STOP_STREAMING]
    
    @classmethod
    def get_management_commands(cls) -> list['WorkerCommand']:
        """Get commands related to worker management"""
        return [cls.RESTART, cls.SHUTDOWN, cls.STATUS_REPORT]
    
    def is_processing_command(self) -> bool:
        """Check if this is a processing command"""
        return self in self.get_processing_commands()
    
    def is_streaming_command(self) -> bool:
        """Check if this is a streaming command"""
        return self in self.get_streaming_commands()
    
    def is_management_command(self) -> bool:
        """Check if this is a management command"""
        return self in self.get_management_commands()


class CommandPriority(Enum):
    """Command priority enumeration"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    
    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented