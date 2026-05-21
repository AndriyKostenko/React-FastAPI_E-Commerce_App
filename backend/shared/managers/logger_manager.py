import logging
import sys
from datetime import datetime, timezone
from typing import Any, override

from pythonjsonlogger.json import JsonFormatter

from shared.middleware.logging_middleware import REQUEST_ID_CTX_VAR, SERVICE_NAME_CTX_VAR

# Store configured loggers to avoid duplicate handler registration.
_loggers: dict[str, logging.Logger] = {}


class _ContextFilter(logging.Filter):
    """Injects request_id and service from active contextvars into every record."""

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = REQUEST_ID_CTX_VAR.get()
        record.service = SERVICE_NAME_CTX_VAR.get()
        return True


class _JsonFormatter(JsonFormatter):
    """Produces clean, consistently-keyed JSON log lines."""

    @override
    def add_fields(self, log_data: dict[str, Any], record: logging.LogRecord, message_dict: dict[str, Any]) -> None:
        super().add_fields(log_data, record, message_dict)
        log_data["timestamp"] = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        log_data["level"] = record.levelname.lower()
        log_data["logger"] = record.name
        # Remove redundant stdlib fields that are already re-mapped above.
        for key in ("levelname", "asctime", "name"):
            log_data.pop(key, None)


def setup_logger(name: str) -> logging.Logger:
    """Return a JSON-structured logger.  Drop-in replacement for the previous setup_logger."""
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(_JsonFormatter(fmt="%(message)s %(levelname)s %(name)s"))
        handler.addFilter(_ContextFilter())
        logger.addHandler(handler)

    _loggers[name] = logger
    return logger
