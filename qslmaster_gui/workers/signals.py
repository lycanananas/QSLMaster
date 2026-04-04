from PyQt6.QtCore import QObject, pyqtSignal


class ProcessorSignals(QObject):
    
    progress = pyqtSignal(str)
    progress_value = pyqtSignal(int, int)
    log = pyqtSignal(str, str)
    
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    cancelled = pyqtSignal(str)
    
    api_check_done = pyqtSignal(bool)
