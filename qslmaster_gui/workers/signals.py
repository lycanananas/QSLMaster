"""
Qt signals for worker communication
"""
from PyQt6.QtCore import QObject, pyqtSignal


class ProcessorSignals(QObject):
    
    progress = pyqtSignal(str)
    log = pyqtSignal(str, str)
    
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    api_check_done = pyqtSignal(bool)
