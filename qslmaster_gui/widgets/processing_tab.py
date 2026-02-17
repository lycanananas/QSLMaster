import logging
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QDateEdit, QCheckBox, QGroupBox, QTextEdit, QProgressBar,
    QFileDialog, QMessageBox, QComboBox
)
from PyQt6.QtCore import Qt, QDate, QThreadPool, pyqtSlot
from PyQt6.QtGui import QFont

from qslmaster_gui.workers.processor_worker import ProcessorWorker

logger = logging.getLogger(__name__)


class ProcessingTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.processor_worker = None
        self.thread_pool = QThreadPool()
        self.current_config = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()


        date_group = QGroupBox("Date Range (Optional)")
        date_layout = QHBoxLayout()

        date_layout.addWidget(QLabel("From Date:"))
        self.from_date_input = QDateEdit()
        self.from_date_input.setDate(QDate.currentDate().addDays(-7))
        self.from_date_input.setCalendarPopup(True)
        date_layout.addWidget(self.from_date_input)

        date_layout.addWidget(QLabel("To Date:"))
        self.to_date_input = QDateEdit()
        self.to_date_input.setDate(QDate.currentDate())
        self.to_date_input.setCalendarPopup(True)
        date_layout.addWidget(self.to_date_input)

        self.use_date_filter = QCheckBox("Use date filter")
        self.use_date_filter.setChecked(True)
        self.use_date_filter.stateChanged.connect(self.on_date_filter_toggled)
        date_layout.addWidget(self.use_date_filter)

        date_group.setLayout(date_layout)
        layout.addWidget(date_group)

        mode_group = QGroupBox("Mode Filter (Optional)")
        mode_layout = QHBoxLayout()
        
        self.mode_all_checkbox = QCheckBox("ALL")
        self.mode_all_checkbox.setChecked(True)
        self.mode_all_checkbox.stateChanged.connect(self.on_mode_all_toggled)
        mode_layout.addWidget(self.mode_all_checkbox)
        
        mode_layout.addSpacing(20)
        
        self.mode_checkboxes = {}
        for mode in ['CW', 'SSB', 'AM', 'FM', 'FT8', 'DIGI']:
            checkbox = QCheckBox(mode)
            checkbox.setChecked(True)
            checkbox.setEnabled(False)
            checkbox.stateChanged.connect(self.on_individual_mode_toggled)
            self.mode_checkboxes[mode] = checkbox
            mode_layout.addWidget(checkbox)
        
        mode_layout.addStretch()
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        output_group = QGroupBox("Output Options")
        output_layout = QVBoxLayout()

        output_layout.addWidget(QLabel("Output ADIF File:"))
        self.output_adif_layout = QHBoxLayout()
        self.output_adif_input = QLineEdit()
        default_adif = Path.home() / f"qsl_output_{datetime.now().strftime('%Y%m%d')}.adif"
        self.output_adif_input.setText(str(default_adif))
        self.output_adif_input.setReadOnly(True)
        self.output_adif_layout.addWidget(self.output_adif_input)
        self.browse_adif_btn = QPushButton("Browse...")
        self.browse_adif_btn.clicked.connect(self.browse_adif_file)
        self.output_adif_layout.addWidget(self.browse_adif_btn)
        output_layout.addLayout(self.output_adif_layout)

        self.generate_pdf = QCheckBox("Generate PDF Labels")
        self.generate_pdf.setChecked(True)
        self.generate_pdf.stateChanged.connect(self.on_generate_pdf_toggled)
        output_layout.addWidget(self.generate_pdf)

        output_layout.addWidget(QLabel("PDF Output File:"))
        self.output_pdf_layout = QHBoxLayout()
        self.output_pdf_input = QLineEdit()
        default_pdf = Path.home() / f"qsl_labels_{datetime.now().strftime('%Y%m%d')}.pdf"
        self.output_pdf_input.setText(str(default_pdf))
        self.output_pdf_input.setReadOnly(True)
        self.output_pdf_layout.addWidget(self.output_pdf_input)
        self.browse_pdf_btn = QPushButton("Browse...")
        self.browse_pdf_btn.clicked.connect(self.browse_pdf_file)
        self.output_pdf_layout.addWidget(self.browse_pdf_btn)
        output_layout.addLayout(self.output_pdf_layout)

        self.debug_labels = QCheckBox("Debug Labels (draw borders)")
        output_layout.addWidget(self.debug_labels)

        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        process_button = QPushButton("Generate QSLs")
        process_button.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        process_button.setMinimumHeight(40)
        process_button.clicked.connect(self.start_processing)
        layout.addWidget(process_button)
        self.process_button = process_button

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(True)
        layout.addWidget(self.progress_bar)

        log_controls = QHBoxLayout()
        log_controls.addWidget(QLabel("Processing Log:"))
        log_controls.addStretch()
        log_controls.addWidget(QLabel("Log Level:"))
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level_combo.setCurrentText("INFO")
        self.log_level_combo.currentTextChanged.connect(self.on_log_level_changed)
        log_controls.addWidget(self.log_level_combo)
        layout.addLayout(log_controls)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)
        self.setLayout(layout)

        self.on_date_filter_toggled()
        self.on_generate_pdf_toggled()

    def on_date_filter_toggled(self):
        enabled = self.use_date_filter.isChecked()
        self.from_date_input.setEnabled(enabled)
        self.to_date_input.setEnabled(enabled)

    def on_generate_pdf_toggled(self):
        enabled = self.generate_pdf.isChecked()
        self.output_pdf_input.setEnabled(enabled)
        self.browse_pdf_btn.setEnabled(enabled)
        self.debug_labels.setEnabled(enabled)

    def on_log_level_changed(self, level_name: str):
        level = getattr(logging, level_name, logging.INFO)
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        for handler in root_logger.handlers:
            handler.setLevel(level)
    
    def on_mode_all_toggled(self):
        checked = self.mode_all_checkbox.isChecked()
        for checkbox in self.mode_checkboxes.values():
            checkbox.blockSignals(True)
            checkbox.setEnabled(not checked)
            if checked:
                checkbox.setChecked(False)
            else:
                checkbox.setChecked(True)
            checkbox.blockSignals(False)
    
    def on_individual_mode_toggled(self):
        all_checked = all(cb.isChecked() for cb in self.mode_checkboxes.values())
        any_unchecked = any(not cb.isChecked() for cb in self.mode_checkboxes.values())
        
        self.mode_all_checkbox.blockSignals(True)
        if all_checked:
            self.mode_all_checkbox.setChecked(True)
        elif any_unchecked:
            self.mode_all_checkbox.setChecked(False)
        self.mode_all_checkbox.blockSignals(False)
    
    def get_selected_modes(self) -> str:
        if self.mode_all_checkbox.isChecked():
            return None
        
        selected = [mode for mode, cb in self.mode_checkboxes.items() if cb.isChecked()]
        return ','.join(selected) if selected else None
    
    def _check_file_overwrite(self, adif_path: str, pdf_path: str) -> bool:
        files_to_check = []
        
        if adif_path and Path(adif_path).exists():
            files_to_check.append(('ADIF', adif_path))
        
        if pdf_path and Path(pdf_path).exists():
            files_to_check.append(('PDF', pdf_path))
        
        if not files_to_check:
            return True
        
        file_list = '\n'.join([f"  • {ftype}: {path}" for ftype, path in files_to_check])
        message = f"The following files already exist:\n{file_list}\n\nDo you want to overwrite them?"
        
        reply = QMessageBox.question(
            self,
            "Files Already Exist",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        return reply == QMessageBox.StandardButton.Yes

    def browse_adif_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save ADIF File",
            str(Path.home()),
            "ADIF Files (*.adif);;All Files (*)"
        )
        if file_path:
            self.output_adif_input.setText(file_path)

    def browse_pdf_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save PDF File",
            str(Path.home()),
            "PDF Files (*.pdf);;All Files (*)"
        )
        if file_path:
            self.output_pdf_input.setText(file_path)

    def start_processing(self):
        if not self.current_config:
            QMessageBox.warning(self, "Error", "No configuration loaded")
            return

        config_to_use = self.current_config.copy()

        if not config_to_use.get('api_key'):
            QMessageBox.warning(
                self,
                "Configuration Error",
                "API Key not found. Please configure it in Settings"
            )
            return

        if not config_to_use.get('wavelog_url'):
            QMessageBox.warning(
                self,
                "Configuration Error",
                "Wavelog URL not found. Please configure it in Settings"
            )
            return

        from_date = None
        to_date = None
        if self.use_date_filter.isChecked():
            from_date = self.from_date_input.date().toPyDate().strftime('%Y-%m-%d')
            to_date = self.to_date_input.date().toPyDate().strftime('%Y-%m-%d')

        modes = self.get_selected_modes()

        output_adif = self.output_adif_input.text()
        output_pdf = self.output_pdf_input.text() if self.generate_pdf.isChecked() else None
        
        if not self._check_file_overwrite(output_adif, output_pdf):
            return

        self.processor_worker = ProcessorWorker(
            config_to_use,
            from_date=from_date,
            to_date=to_date,
            modes=modes,
            output_adif=output_adif,
            generate_pdf=output_pdf,
            debug_labels=self.debug_labels.isChecked(),
        )

        self.processor_worker.signals.progress.connect(self.on_progress)
        self.processor_worker.signals.progress_value.connect(self.on_progress_value)
        self.processor_worker.signals.log.connect(self.on_log)
        self.processor_worker.signals.finished.connect(self.on_finished)
        self.processor_worker.signals.error.connect(self.on_error)

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.log_output.clear()

        self.process_button.setEnabled(False)
        self.thread_pool.start(self.processor_worker)

    @pyqtSlot(str)
    def on_progress(self, message: str):
        self.log_output.append(f"[PROGRESS] {message}")

    @pyqtSlot(int, int)
    def on_progress_value(self, current: int, total: int):
        if total > 0:
            percentage = int(current / total * 100)
            self.progress_bar.setValue(percentage)

    @pyqtSlot(str, str)
    def on_log(self, level: str, message: str):
        self.log_output.append(f"[{level}] {message}")

    @pyqtSlot(dict)
    def on_finished(self, result: dict):
        self.progress_bar.setVisible(True)
        self.process_button.setEnabled(True)

        if result['success']:
            stats_text = "Processing completed successfully!\n\n"
            stats_text += f"Total QSOs to send: {result['stats'].get('total_to_send', 0)}\n"

            for country, stats in result['stats'].items():
                if country != 'total_to_send' and isinstance(stats, dict):
                    stats_text += f"{country}: {stats.get('to_send', 0)}/{stats.get('total', 0)}\n"

            stats_text += f"\nOutput files:\n"
            stats_text += f"  ADIF: {result['output_adif']}\n"
            if result['output_pdf']:
                stats_text += f"  PDF: {result['output_pdf']}\n"

            QMessageBox.information(self, "Processing Complete", stats_text)
        else:
            QMessageBox.critical(self, "Processing Failed", f"Error: {result.get('error')}")

    @pyqtSlot(str)
    def on_error(self, error_message: str):
        self.progress_bar.setVisible(False)
        self.process_button.setEnabled(True)
        QMessageBox.critical(self, "Processing Error", f"An error occurred: {error_message}")
