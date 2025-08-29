"""
Correlation ID system for tracking requests across services
"""
import uuid
from contextvars import ContextVar
from typing import Optional
import structlog

# Context variable to store correlation ID
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)

def generate_correlation_id() -> str:
    """Generate a new correlation ID"""
    return str(uuid.uuid4())

def set_correlation_id(cid: str) -> None:
    """Set correlation ID in context"""
    correlation_id.set(cid)

def get_correlation_id() -> Optional[str]:
    """Get current correlation ID"""
    return correlation_id.get()

def get_or_create_correlation_id() -> str:
    """Get existing correlation ID or create a new one"""
    cid = get_correlation_id()
    if cid is None:
        cid = generate_correlation_id()
        set_correlation_id(cid)
    return cid

# Structured logger with correlation ID processor
def add_correlation_id(logger, method_name, event_dict):
    """Add correlation ID to log events"""
    cid = get_correlation_id()
    if cid:
        event_dict['correlation_id'] = cid
    return event_dict

# Configure structured logger
structlog.configure(
    processors=[
        add_correlation_id,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

def get_structured_logger(name: str = __name__):
    """Get a structured logger with correlation ID support"""
    return structlog.get_logger(name)