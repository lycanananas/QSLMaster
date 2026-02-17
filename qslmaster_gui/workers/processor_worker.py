import logging
from typing import Optional
from PyQt6.QtCore import QRunnable

from qslmaster_cli.qslmaster_core import QSLProcessor
from qslmaster_cli.logging_handler import LogHandler
from .signals import ProcessorSignals


logger = logging.getLogger(__name__)


class ProcessorWorker(QRunnable):
    
    def __init__(
        self,
        config: dict,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        output_adif: Optional[str] = None,
        generate_pdf: Optional[str] = None,
        debug_labels: bool = False,
    ):
        super().__init__()
        self.config = config
        self.from_date = from_date
        self.to_date = to_date
        self.output_adif = output_adif
        self.generate_pdf = generate_pdf
        self.debug_labels = debug_labels
        self.should_stop = False
        
        self.signals = ProcessorSignals()
    
    def run(self):
        if self.should_stop:
            self.signals.error.emit("Processing cancelled")
            return
        
        LogHandler.set_callback(lambda lvl, msg: self.signals.log.emit(lvl, msg))
            
        try:
            processor = QSLProcessor(
                self.config,
                progress_callback=self.signals.progress.emit,
                log_callback=lambda lvl, msg: self.signals.log.emit(lvl, msg),
                progress_value_callback=self.signals.progress_value.emit,
            )
            
            result = processor.process(
                from_date=self.from_date,
                to_date=self.to_date,
                output_adif=self.output_adif,
                generate_pdf=self.generate_pdf,
                debug_labels=self.debug_labels,
                preview_pdf=False,
            )
            
            if not self.should_stop:
                self.signals.finished.emit(result)
            else:
                self.signals.error.emit("Processing cancelled")
            
        except Exception as e:
            if not self.should_stop:
                logger.exception(f"Worker error: {e}")
                self.signals.error.emit(str(e))
    
    def stop(self):
        self.should_stop = True
