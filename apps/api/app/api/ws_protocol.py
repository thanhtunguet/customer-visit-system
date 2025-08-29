"""
WebSocket Protocol with Pydantic Schemas for Worker Communication
Based on GPT Plan Section 3: Control plane protocol (backend ↔ worker)
"""
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field
from enum import Enum


# Message Types as per GPT Plan

class MessageType(str, Enum):
    """WebSocket message types"""
    # Worker → Server
    REGISTER = "REGISTER"
    HEARTBEAT = "HEARTBEAT" 
    ACK = "ACK"
    EVENT = "EVENT"
    
    # Server → Worker  
    START = "START"
    STOP = "STOP"
    RELOAD = "RELOAD"
    DRAIN = "DRAIN"


class IntentStatus(str, Enum):
    """Status values for ACK messages"""
    SUCCESS = "success"
    ERROR = "error"
    PROCESSING = "processing"


class EventType(str, Enum):
    """Event types for worker events"""
    PIPELINE_READY = "pipeline_ready"
    PIPELINE_ERROR = "pipeline_error"
    RTSP_ERROR = "rtsp_error"
    FRAME_PROCESSED = "frame_processed"
    WORKER_STATUS_CHANGE = "worker_status_change"


class SourceType(str, Enum):
    """Camera source types"""
    RTSP = "rtsp"
    WEBCAM = "webcam"


# Base Message Schema

class BaseMessage(BaseModel):
    """Base message schema with common fields"""
    type: MessageType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None


# Worker → Server Messages

class RegisterMessage(BaseMessage):
    """REGISTER message from worker to server"""
    type: MessageType = MessageType.REGISTER
    worker_id: str
    site_id: int
    version: str
    labels: Optional[Dict[str, str]] = None
    capacity: Optional[Dict[str, Any]] = Field(
        default={"slots": 1, "cpu": 0, "gpu": 0, "mem": 0}
    )


class LeaseRenewal(BaseModel):
    """Lease renewal item for heartbeat"""
    camera_id: int
    generation: int


class WorkerMetrics(BaseModel):
    """Worker metrics for heartbeat"""
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    active_cameras: int = 0
    frames_processed: int = 0
    errors_count: int = 0


class HeartbeatMessage(BaseMessage):
    """HEARTBEAT message from worker to server"""
    type: MessageType = MessageType.HEARTBEAT
    worker_id: str
    metrics: WorkerMetrics
    renew: List[LeaseRenewal] = Field(default_factory=list)


class AckMessage(BaseMessage):
    """ACK message from worker to server"""
    type: MessageType = MessageType.ACK
    intent_id: str
    status: IntentStatus
    details: Optional[str] = None
    error_code: Optional[str] = None


class EventMessage(BaseMessage):
    """EVENT message from worker to server"""
    type: MessageType = MessageType.EVENT
    camera_id: int
    generation: int
    seq: int  # Sequence number for ordering
    event_type: EventType
    payload: Dict[str, Any]


# Server → Worker Messages

class CameraSource(BaseModel):
    """Camera source configuration"""
    type: SourceType
    rtsp_url: Optional[str] = None  # For RTSP cameras
    device_index: Optional[int] = None  # For webcam cameras


class StartMessage(BaseMessage):
    """START message from server to worker"""
    type: MessageType = MessageType.START
    intent_id: str
    camera_id: int
    generation: int
    source: CameraSource
    model_version: Optional[str] = None
    params: Optional[Dict[str, Any]] = None


class StopMessage(BaseMessage):
    """STOP message from server to worker"""
    type: MessageType = MessageType.STOP
    intent_id: str
    camera_id: int
    generation: int
    reason: str


class ReloadMessage(BaseMessage):
    """RELOAD message from server to worker"""
    type: MessageType = MessageType.RELOAD
    intent_id: str
    config: Optional[Dict[str, Any]] = None


class DrainMessage(BaseMessage):
    """DRAIN message from server to worker"""
    type: MessageType = MessageType.DRAIN
    intent_id: str
    timeout_seconds: Optional[int] = 30


# Union type for all possible messages
WorkerMessage = Union[RegisterMessage, HeartbeatMessage, AckMessage, EventMessage]
ServerMessage = Union[StartMessage, StopMessage, ReloadMessage, DrainMessage]
WSMessage = Union[WorkerMessage, ServerMessage]


# Message Factory Functions

def create_register_message(
    worker_id: str,
    site_id: int,
    version: str,
    labels: Optional[Dict[str, str]] = None,
    capacity: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None
) -> RegisterMessage:
    """Create a REGISTER message"""
    return RegisterMessage(
        worker_id=worker_id,
        site_id=site_id,
        version=version,
        labels=labels,
        capacity=capacity,
        correlation_id=correlation_id
    )


def create_heartbeat_message(
    worker_id: str,
    metrics: WorkerMetrics,
    renewals: List[LeaseRenewal] = None,
    correlation_id: Optional[str] = None
) -> HeartbeatMessage:
    """Create a HEARTBEAT message"""
    return HeartbeatMessage(
        worker_id=worker_id,
        metrics=metrics,
        renew=renewals or [],
        correlation_id=correlation_id
    )


def create_ack_message(
    intent_id: str,
    status: IntentStatus,
    details: Optional[str] = None,
    error_code: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> AckMessage:
    """Create an ACK message"""
    return AckMessage(
        intent_id=intent_id,
        status=status,
        details=details,
        error_code=error_code,
        correlation_id=correlation_id
    )


def create_event_message(
    camera_id: int,
    generation: int,
    seq: int,
    event_type: EventType,
    payload: Dict[str, Any],
    correlation_id: Optional[str] = None
) -> EventMessage:
    """Create an EVENT message"""
    return EventMessage(
        camera_id=camera_id,
        generation=generation,
        seq=seq,
        event_type=event_type,
        payload=payload,
        correlation_id=correlation_id
    )


def create_start_message(
    intent_id: str,
    camera_id: int,
    generation: int,
    source: CameraSource,
    model_version: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None
) -> StartMessage:
    """Create a START message"""
    return StartMessage(
        intent_id=intent_id,
        camera_id=camera_id,
        generation=generation,
        source=source,
        model_version=model_version,
        params=params,
        correlation_id=correlation_id
    )


def create_stop_message(
    intent_id: str,
    camera_id: int,
    generation: int,
    reason: str,
    correlation_id: Optional[str] = None
) -> StopMessage:
    """Create a STOP message"""
    return StopMessage(
        intent_id=intent_id,
        camera_id=camera_id,
        generation=generation,
        reason=reason,
        correlation_id=correlation_id
    )


def create_drain_message(
    intent_id: str,
    timeout_seconds: int = 30,
    correlation_id: Optional[str] = None
) -> DrainMessage:
    """Create a DRAIN message"""
    return DrainMessage(
        intent_id=intent_id,
        timeout_seconds=timeout_seconds,
        correlation_id=correlation_id
    )


# Message Parsing and Validation

def parse_message(data: Dict[str, Any]) -> WSMessage:
    """
    Parse incoming WebSocket message data into appropriate Pydantic model
    
    Args:
        data: Raw message data from WebSocket
        
    Returns:
        Parsed message object
        
    Raises:
        ValueError: If message type is unknown or validation fails
    """
    message_type = data.get("type")
    
    if message_type == MessageType.REGISTER:
        return RegisterMessage.parse_obj(data)
    elif message_type == MessageType.HEARTBEAT:
        return HeartbeatMessage.parse_obj(data)
    elif message_type == MessageType.ACK:
        return AckMessage.parse_obj(data)
    elif message_type == MessageType.EVENT:
        return EventMessage.parse_obj(data)
    elif message_type == MessageType.START:
        return StartMessage.parse_obj(data)
    elif message_type == MessageType.STOP:
        return StopMessage.parse_obj(data)
    elif message_type == MessageType.RELOAD:
        return ReloadMessage.parse_obj(data)
    elif message_type == MessageType.DRAIN:
        return DrainMessage.parse_obj(data)
    else:
        raise ValueError(f"Unknown message type: {message_type}")


def serialize_message(message: WSMessage) -> Dict[str, Any]:
    """
    Serialize message object to dict for WebSocket transmission
    
    Args:
        message: Pydantic message object
        
    Returns:
        Serialized message dictionary
    """
    return message.dict(exclude_none=True)