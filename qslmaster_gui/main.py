import os
import sys
import logging
import signal
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon

from .ui.main_window import QSLMasterMainWindow
from .workers.task_worker import TaskWorker
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

    icon_candidates = [
        Path('/usr/share/pixmaps/qslmaster.png'),
        Path(__file__).resolve().parent / 'resources' / 'icon.png',
        Path(__file__).resolve().parent / 'resources' / 'icon.ico',
    ]
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        icon_candidates.append(Path(meipass) / 'qslmaster_gui' / 'resources' / 'icon.png')
        icon_candidates.append(Path(meipass) / 'qslmaster_gui' / 'resources' / 'icon.ico')
        icon_candidates.append(Path(meipass) / 'icon.png')
        icon_candidates.append(Path(meipass) / 'qslmaster.ico')

    icon_path = next((candidate for candidate in icon_candidates if candidate.exists()), None)
    if icon_path:
        app.setWindowIcon(QIcon(str(icon_path)))

    window = QSLMasterMainWindow()
    if icon_path:
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()
    
    def signal_handler(signum, frame):
        app.quit()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(500)
    
    exit_code = app.exec()
    window.processing_tab.shutdown(timeout_ms=1000)
    if TaskWorker.any_running():
        os._exit(exit_code)
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
