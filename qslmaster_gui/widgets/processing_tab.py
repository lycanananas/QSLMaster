import logging
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QDateEdit, QCheckBox, QGroupBox, QTextEdit, QProgressBar,
    QFileDialog, QMessageBox, QComboBox, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QDate, QThreadPool, pyqtSlot
from PyQt6.QtGui import QFont
from qslmaster_gui.workers.processor_worker import ProcessorWorker
from qslmaster_cli.qslmaster_core import QSLProcessor
from qslmaster_cli.wavelog import WavelogAPI
logger = logging.getLogger(__name__)


class ProcessingTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.processor_worker = None
        self.thread_pool = QThreadPool()
        self.current_config = None
        self.stations_loaded = False
        self.qrz_error_count = 0
        self.pzk_error_count = 0
        self.qrz_disabled = False
        self.pzk_disabled = False
        self.init_ui()

    def set_config(self, config):
        self.current_config = config
        if not config or not config.get('api_key') or not config.get('wavelog_url'):
            self.station_list.clear()
            self.all_stations_check.setChecked(True)
            self.station_list.setEnabled(False)
            self.stations_loaded = False
        else:
            self.load_station_list(config)
    def load_station_list(self, config):
        logger.info("Loading station list from Wavelog...")
        self.station_list.clear()
        try:
            processor = QSLProcessor(config)
            processor.api_client = WavelogAPI(config['wavelog_url'], config['api_key'])
            stations = processor.list_stations()
            logger.info(f"Retrieved {len(stations)} stations from Wavelog")
            for s in stations:
                label = f"[{s['station_callsign']}] - {s['station_profile_name']}"
                logger.info(f"Added station: {label}")
                item = QListWidgetItem(label)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                self.station_list.addItem(item)
            self.all_stations_check.setChecked(True)
            self.station_list.setEnabled(False)
            logger.info("Station list loaded successfully")
            self.stations_loaded = True
        except Exception as e:
            logger.error(f"Failed to load station list: {e}")
            self.all_stations_check.setChecked(True)
            self.station_list.setEnabled(False)
            self.stations_loaded = False
    def on_refresh_station_list(self):
        if self.current_config:
            self.load_station_list(self.current_config)

    def init_ui(self):
        layout = QVBoxLayout()

        selection_layout = QHBoxLayout()

        station_group = QGroupBox("Stations")
        station_layout = QVBoxLayout()
        station_header = QHBoxLayout()
        self.all_stations_check = QCheckBox("All stations")
        self.all_stations_check.setChecked(True)
        self.all_stations_check.stateChanged.connect(self.on_all_stations_toggled)
        station_header.addWidget(self.all_stations_check)
        self.refresh_station_btn = QPushButton("Refresh")
        self.refresh_station_btn.clicked.connect(self.on_refresh_station_list)
        station_header.addWidget(self.refresh_station_btn)
        station_header.addStretch()
        station_layout.addLayout(station_header)
        self.station_list = QListWidget()
        self.station_list.setMinimumHeight(120)
        self.station_list.setEnabled(False)
        station_layout.addWidget(self.station_list)
        station_group.setLayout(station_layout)
        selection_layout.addWidget(station_group)

        mode_group = QGroupBox("Modes")
        mode_layout = QVBoxLayout()
        self.all_modes_check = QCheckBox("All modes")
        self.all_modes_check.setChecked(True)
        self.all_modes_check.stateChanged.connect(self.on_all_modes_toggled)
        mode_layout.addWidget(self.all_modes_check)
        self.mode_list = QListWidget()
        self.mode_list.setEnabled(False)
        for mode in ['CW', 'SSB', 'USB', 'LSB', 'AM', 'FM', 'FT8', 'JT65', 'RTTY', 'PSK31', 'DIGI', 'DATA', 'SSTV', 'HELL']:
            item = QListWidgetItem(mode)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.mode_list.addItem(item)
        mode_layout.addWidget(self.mode_list)
        mode_group.setLayout(mode_layout)
        mode_group.setMaximumWidth(220)
        selection_layout.addWidget(mode_group)

        layout.addLayout(selection_layout)

        date_group = QGroupBox("Date Range")
        date_layout = QVBoxLayout()

        self.use_date_filter = QCheckBox("Use date filter")
        self.use_date_filter.setChecked(True)
        self.use_date_filter.stateChanged.connect(self.on_date_filter_toggled)
        date_layout.addWidget(self.use_date_filter)

        from_layout = QVBoxLayout()
        from_layout.addWidget(QLabel("From Date:"))
        self.from_date_input = QDateEdit()
        self.from_date_input.setDate(QDate.currentDate().addDays(-7))
        self.from_date_input.setCalendarPopup(True)
        from_layout.addWidget(self.from_date_input)
        date_layout.addLayout(from_layout)

        to_layout = QVBoxLayout()
        to_layout.addWidget(QLabel("To Date:"))
        self.to_date_input = QDateEdit()
        self.to_date_input.setDate(QDate.currentDate())
        self.to_date_input.setCalendarPopup(True)
        to_layout.addWidget(self.to_date_input)
        date_layout.addLayout(to_layout)

        date_group.setLayout(date_layout)
        date_group.setMinimumWidth(250)

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

        options_layout = QHBoxLayout()
        options_layout.addWidget(date_group)
        options_layout.addWidget(output_group)
        layout.addLayout(options_layout)

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
    
    def on_all_stations_toggled(self):
        self.station_list.setEnabled(not self.all_stations_check.isChecked())

    def on_all_modes_toggled(self):
        self.mode_list.setEnabled(not self.all_modes_check.isChecked())
    
    def get_selected_modes(self) -> str:
        if self.all_modes_check.isChecked():
            return None
        
        selected = []
        for i in range(self.mode_list.count()):
            item = self.mode_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())
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

        if not self.stations_loaded:
            self.load_station_list(config_to_use)

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

        selected_stations = []
        if self.all_stations_check.isChecked():
            selected_stations = ['all']
        else:
            for i in range(self.station_list.count()):
                item = self.station_list.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    selected_stations.append(item.text().split(' ')[0])
        station_selector = selected_stations if selected_stations else ['all']

        self.processor_worker = ProcessorWorker(
            config_to_use,
            from_date=from_date,
            to_date=to_date,
            modes=modes,
            output_adif=output_adif,
            generate_pdf=output_pdf,
            debug_labels=self.debug_labels.isChecked(),
            station_selector=station_selector,
        )

        self.processor_worker.signals.progress.connect(self.on_progress)
        self.processor_worker.signals.progress_value.connect(self.on_progress_value)
        self.processor_worker.signals.log.connect(self.on_log)
        self.processor_worker.signals.finished.connect(self.on_finished)
        self.processor_worker.signals.error.connect(self.on_error)

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.log_output.clear()
        self.qrz_error_count = 0
        self.pzk_error_count = 0
        self.qrz_disabled = False
        self.pzk_disabled = False

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
        message_lower = message.lower()
        if "qrz result:" in message_lower and "lookup error" in message_lower:
            self.qrz_error_count += 1
        if "pzk result:" in message_lower and "lookup error" in message_lower:
            self.pzk_error_count += 1
        if "ignoring qrz lookups for remaining callsigns" in message_lower:
            self.qrz_disabled = True
        if "ignoring pzk lookups for remaining callsigns" in message_lower:
            self.pzk_disabled = True

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

            if self.qrz_error_count > 0 or self.pzk_error_count > 0:
                stats_text += "\nAPI errors:\n"
                if self.qrz_error_count > 0:
                    qrz_status = " (ignored after 3 errors)" if self.qrz_disabled else ""
                    stats_text += f"  QRZ: {self.qrz_error_count} error(s){qrz_status}\n"
                if self.pzk_error_count > 0:
                    pzk_status = " (ignored after 3 errors)" if self.pzk_disabled else ""
                    stats_text += f"  PZK: {self.pzk_error_count} error(s){pzk_status}\n"

            QMessageBox.information(self, "Processing Complete", stats_text)
        else:
            QMessageBox.critical(self, "Processing Failed", f"Error: {result.get('error')}")

    @pyqtSlot(str)
    def on_error(self, error_message: str):
        self.progress_bar.setVisible(False)
        self.process_button.setEnabled(True)
        QMessageBox.critical(self, "Processing Error", f"An error occurred: {error_message}")
