import logging
import sys
from pathlib import Path
from typing import Dict

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Create logs directory relative to the project root
LOG_DIR = PROJECT_ROOT / "logs"

try:
    LOG_DIR.mkdir(exist_ok=True, mode=0o755)
except OSError:
    LOG_DIR = Path("/tmp/logs")
    try:
        LOG_DIR.mkdir(exist_ok=True, mode=0o755)
    except OSError:
        LOG_DIR = None

# Store configured loggers
_loggers: Dict[str, logging.Logger] = {}

def setup_logger(name: str) -> logging.Logger:
    """Configure logger with file and console handlers"""
    if name in _loggers:
        return _loggers[name]
    
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        
        # File handler — skipped silently when the filesystem is read-only
        # (e.g. Docker containers that mount /app/shared as :ro).
        # Stdout is always available and is the correct sink in containers.
        if LOG_DIR is not None:
            try:
                file_handler = logging.FileHandler(
                    LOG_DIR / "app.log",
                    mode='a'
                )
                file_handler.setLevel(logging.DEBUG)
                file_handler.setFormatter(logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                ))
                logger.addHandler(file_handler)
            except OSError:
                pass  # read-only fs or no permission — stdout only
        
        # Console handler (always present)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(logging.Formatter(
            '%(levelname)s: %(message)s'
        ))
        logger.addHandler(console_handler)
    
    _loggers[name] = logger
    return logger