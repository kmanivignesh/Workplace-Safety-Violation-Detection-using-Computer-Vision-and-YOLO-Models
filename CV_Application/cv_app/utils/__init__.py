"""
utils/__init__.py – expose key helpers at the package level.
"""
from .detection   import load_model, process_frame
from .voice_alert import get_alert_engine
from .logger      import log_event, get_recent, get_log_path

__all__ = [
    "load_model", "process_frame",
    "get_alert_engine",
    "log_event", "get_recent", "get_log_path",
]
