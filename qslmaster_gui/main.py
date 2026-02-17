#!/usr/bin/env python3
"""
QSLMaster GUI Application
PyQt6-based graphical interface for QSL processing
"""
import sys
import logging
import signal
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from .ui.main_window import QSLMasterMainWindow


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
    app.setApplicationName("QSLMaster")
    app.setApplicationVersion("1.0.0")
    
    window = QSLMasterMainWindow()
    window.show()
    
    def signal_handler(signum, frame):
        window.close()
        app.quit()
    
    signal.signal(signal.SIGINT, signal_handler)
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
