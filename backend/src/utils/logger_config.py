import logging
import sys
from pathlib import Path
from typing import Dict

# Create logs directory if it doesn't exist
LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Store configured loggers
_loggers: Dict[str, logging.Logger] = {}

def setup_logger(name: str) -> logging.Logger:
    """Configure logger with file and console handlers"""
    # Return existing logger if already configured
    if name in _loggers:
        return _loggers[name]
    
    logger = logging.getLogger(name)
    
    # Only configure if no handlers exist
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        
        # Prevent propagation to root logger
        logger.propagate = False
        
        # File handler
        file_handler = logging.FileHandler(
            LOG_DIR / "app.log",
            mode='a'
        )
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_format)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_format = logging.Formatter(
            '%(levelname)s: %(message)s'
        )
        console_handler.setFormatter(console_format)
        
        # Add handlers to logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    # Cache the configured logger
    _loggers[name] = logger
    
    return logger