from threading import Lock
from typing import Any, Dict, override


class SingletonMetaClass(type):
    """
    A thread-safe metaclass for creating singleton classes.
    Ensures that only one instance of the class can be created.
    """
    _instances: dict[type, Any] = {}
    _lock: Lock = Lock()

    @override
    def __call__(cls, *args, **kwargs):
        # Double-checked locking pattern for thread safety
        if cls not in cls._instances:
            with cls._lock:
                # Check again inside the lock to prevent race conditions
                if cls not in cls._instances:
                    instance = super().__call__(*args, **kwargs)
                    cls._instances[cls] = instance
        return cls._instances[cls]
