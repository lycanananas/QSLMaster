import logging
from typing import Optional, Callable


class LogHandler:
    _instance = None
    _callback: Optional[Callable[[str, str], None]] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def set_callback(cls, callback: Optional[Callable[[str, str], None]]):
        cls._callback = callback
    
    def log(self, level: str, msg: str):
        if LogHandler._callback:
            LogHandler._callback(level, msg)
        else:
            logger = logging.getLogger('qslmaster_cli')
            getattr(logger, level.lower(), logger.info)(msg)
