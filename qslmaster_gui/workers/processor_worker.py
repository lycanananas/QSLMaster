import logging
import multiprocessing as mp
from queue import Empty
from typing import Optional

from PyQt6.QtCore import QObject, QTimer

from qslmaster_cli.qslmaster_core import QSLProcessor
from .signals import ProcessorSignals


logger = logging.getLogger(__name__)


def _run_processor(
    event_queue,
    config: dict,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    modes: Optional[str] = None,
    output_adif: Optional[str] = None,
    generate_pdf: Optional[str] = None,
    pdf_page_specs=None,
    debug_labels: bool = False,
    station_selector=None,
):
    def emit_progress(message: str) -> None:
        event_queue.put(("progress", message))

    def emit_log(level: str, message: str) -> None:
        event_queue.put(("log", level, message))

    def emit_progress_value(current: int, total: int) -> None:
        event_queue.put(("progress_value", current, total))

    try:
        processor = QSLProcessor(
            config,
            progress_callback=emit_progress,
            log_callback=emit_log,
            progress_value_callback=emit_progress_value,
        )

        result = processor.process(
            from_date=from_date,
            to_date=to_date,
            modes=modes,
            station_selector=station_selector,
            output_adif=output_adif,
            generate_pdf=generate_pdf,
            pdf_page_specs=pdf_page_specs,
            debug_labels=debug_labels,
            preview_pdf=False,
        )
        event_queue.put(("finished", result))
    except Exception as e:
        logger.exception(f"Worker process error: {e}")
        event_queue.put(("error", str(e)))


class ProcessorWorker(QObject):
    def __init__(
        self,
        config: dict,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        modes: Optional[str] = None,
        output_adif: Optional[str] = None,
        generate_pdf: Optional[str] = None,
        pdf_page_specs=None,
        debug_labels: bool = False,
        station_selector=None,
    ):
        super().__init__()
        self.config = config
        self.from_date = from_date
        self.to_date = to_date
        self.modes = modes
        self.output_adif = output_adif
        self.generate_pdf = generate_pdf
        self.pdf_page_specs = pdf_page_specs
        self.debug_labels = debug_labels
        self.station_selector = station_selector
        self.signals = ProcessorSignals()
        self.process = None
        self.event_queue = None
        self.abort_requested = False
        self._completion_emitted = False
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(100)
        self.poll_timer.timeout.connect(self._poll_events)

    def start(self):
        if self.process is not None:
            return

        ctx = mp.get_context('spawn')
        self.event_queue = ctx.Queue()
        self.abort_requested = False
        self._completion_emitted = False
        self.process = ctx.Process(
            target=_run_processor,
            args=(
                self.event_queue,
                self.config,
                self.from_date,
                self.to_date,
                self.modes,
                self.output_adif,
                self.generate_pdf,
                self.pdf_page_specs,
                self.debug_labels,
                self.station_selector,
            ),
        )
        self.process.start()
        self.poll_timer.start()

    def _poll_events(self):
        if self.event_queue is not None:
            while True:
                try:
                    event = self.event_queue.get_nowait()
                except Empty:
                    break

                event_type = event[0]
                if event_type == 'progress':
                    self.signals.progress.emit(event[1])
                elif event_type == 'progress_value':
                    self.signals.progress_value.emit(event[1], event[2])
                elif event_type == 'log':
                    self.signals.log.emit(event[1], event[2])
                elif event_type == 'finished':
                    self._completion_emitted = True
                    result = event[1]
                    self._cleanup_process()
                    if self.abort_requested:
                        self.signals.cancelled.emit("Processing aborted")
                    else:
                        self.signals.finished.emit(result)
                    return
                elif event_type == 'error':
                    self._completion_emitted = True
                    self._cleanup_process()
                    if self.abort_requested:
                        self.signals.cancelled.emit("Processing aborted")
                    else:
                        self.signals.error.emit(event[1])
                    return

        if self.process is not None and not self.process.is_alive() and not self._completion_emitted:
            exit_code = self.process.exitcode
            self._cleanup_process()
            if self.abort_requested:
                self.signals.cancelled.emit("Processing aborted")
            elif exit_code == 0:
                self.signals.error.emit("Processing finished without result")
            else:
                self.signals.error.emit(f"Processing process exited with code {exit_code}")

    def _cleanup_process(self):
        self.poll_timer.stop()
        if self.process is not None:
            try:
                self.process.join(timeout=0.1)
            except Exception:
                pass
            self.process = None
        if self.event_queue is not None:
            try:
                self.event_queue.close()
            except Exception:
                pass
            self.event_queue = None

    def stop(self):
        if self.process is None:
            return

        self.abort_requested = True
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=0.3)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=0.3)
        self._poll_events()
        if not self._completion_emitted:
            self._completion_emitted = True
            self._cleanup_process()
            self.signals.cancelled.emit("Processing aborted")
