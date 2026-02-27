import sys
import os
import logging
import signal
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon

from .ui.main_window import QSLMasterMainWindow
from qslmaster_version import get_version


def setup_logging():
    log_dir = Path.home() / '.local' / 'share' / 'qslmaster'
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / 'gui.log'
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stderr),
        ]
    )


def main():
    setup_logging()
    
    app = QApplication(sys.argv)
    app.setApplicationName("qslmaster")
    app.setApplicationDisplayName("QSLMaster")
    app.setApplicationVersion(get_version())
    app.setDesktopFileName("qslmaster")

    window = QSLMasterMainWindow()
    window.show()
    
    def signal_handler(signum, frame):
        if (window.processing_tab.processor_worker and 
            window.processing_tab.thread_pool.activeThreadCount() > 0):
            window.processing_tab.processor_worker.stop()
            if not window.processing_tab.thread_pool.waitForDone(100):
                os._exit(1)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(500)
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
