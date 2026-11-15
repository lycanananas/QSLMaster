from typing import Any, Callable, Set

from PyQt6.QtCore import QThread, pyqtSignal


class TaskWorker(QThread):

    succeeded = pyqtSignal(object)
    failed = pyqtSignal(object)
    progress = pyqtSignal(str)
    progress_value = pyqtSignal(int, int)
    log = pyqtSignal(str, str)

    running_workers: Set['TaskWorker'] = set()

    def __init__(self, task: Callable[['TaskWorker'], Any]):
        super().__init__()
        self.task = task
        self._stop_requested = False
        TaskWorker.running_workers.add(self)
        self.finished.connect(self.deleteLater)
        self.destroyed.connect(lambda: TaskWorker.running_workers.discard(self))

    def request_stop(self) -> None:
        self._stop_requested = True

    def should_stop(self) -> bool:
        return self._stop_requested

    def run(self) -> None:
        try:
            result = self.task(self)
        except Exception as e:
            self.failed.emit(e)
            return
        self.succeeded.emit(result)

    @classmethod
    def any_running(cls) -> bool:
        for worker in list(cls.running_workers):
            try:
                if worker.isRunning():
                    return True
            except RuntimeError:
                cls.running_workers.discard(worker)
        return False

    @classmethod
    def stop_all(cls, timeout_ms: int = 3000) -> None:
        for worker in list(cls.running_workers):
            try:
                worker.request_stop()
                worker.wait(timeout_ms)
            except RuntimeError:
                cls.running_workers.discard(worker)
