import threading
from typing import Any, Dict


class SingletonMetaClass(type):
    """
    A thread-safe metaclass for creating singleton classes.
    Ensures that only one instance of the class can be created.
    """
    _instances: Dict[type, Any] = {}
    _lock = threading.Lock()
    
    def __call__(cls, *args, **kwargs): #type: ignore
        # Double-checked locking pattern for thread safety
        if cls not in cls._instances:
            with cls._lock:
                # Check again inside the lock to prevent race conditions
                if cls not in cls._instances:
                    instance = super().__call__(*args, **kwargs)
                    cls._instances[cls] = instance
        return cls._instances[cls]
    
    """
    A singleton metaclass that allows resetting instances (useful for testing).
    """
    _instances: Dict[type, Any] = {}
    _lock = threading.Lock()
    
    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]
    
    def reset_instance(cls):
        """Reset the singleton instance (useful for testing)"""
        with cls._lock:
            if cls in cls._instances:
                del cls._instances[cls]
    
    def reset_all_instances(cls):
        """Reset all singleton instances"""
        with cls._lock:
            cls._instances.clear()