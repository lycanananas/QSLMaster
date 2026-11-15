import logging
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QDateEdit, QCheckBox, QGroupBox, QTextEdit, QProgressBar,
    QFileDialog, QMessageBox, QComboBox, QListWidget, QListWidgetItem,
    QDialog, QDialogButtonBox, QRadioButton, QSpinBox
)
from PyQt6.QtCore import Qt, QDate, pyqtSlot
from qslmaster_gui.dialogs.pdf_options_dialog import PdfOptionsDialog
from qslmaster_gui.dialogs.mark_sent_dialog import MarkSentDialog
from qslmaster_gui.workers.processor_worker import ProcessorWorker
from qslmaster_gui.workers.task_worker import TaskWorker
from qslmaster_cli.qslmaster_core import QSLProcessor
from qslmaster_cli.wavelog import create_wavelog_api, WavelogAuthError
logger = logging.getLogger(__name__)


class ProcessingTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.processor_worker = None
        self.current_config = None
        self.stations_loaded = False
        self.qrz_error_count = 0
        self.pzk_error_count = 0
        self.qrz_disabled = False
        self.pzk_disabled = False
        self.processing_active = False
        self.pdf_draw_borders = False
        self.pdf_page_options_text = ''
        self.pdf_page_specs = []
        self.station_request_id = 0
        self.mark_sent_active = False
        self.mark_sent_worker = None
        self.init_ui()

    def start_background_task(self, task, on_success, on_failure, on_progress=None, on_progress_value=None, on_log=None) -> TaskWorker:
        worker = TaskWorker(task)
        worker.succeeded.connect(on_success)
        worker.failed.connect(on_failure)
        if on_progress:
            worker.progress.connect(on_progress)
        if on_progress_value:
            worker.progress_value.connect(on_progress_value)
        if on_log:
            worker.log.connect(on_log)
        worker.start()
        return worker

    def shutdown(self, timeout_ms: int = 3000):
        if self.processor_worker:
            self.processor_worker.stop()
        TaskWorker.stop_all(timeout_ms)

    @staticmethod
    def _normalize_source(source: str) -> str:
        source = str(source or 'wavelog').strip().lower()
        if source in {'adif', 'file'}:
            return 'adif_file'
        return source

    def _has_wavelog_config(self, config) -> bool:
        return bool(config and config.get('api_key') and config.get('wavelog_url'))

    def _set_processing_buttons_enabled(self, enabled: bool):
        self.process_wavelog_button.setEnabled(enabled)
        self.process_adif_button.setEnabled(enabled)
        self.mark_sent_button.setEnabled(enabled and self._has_wavelog_config(self.current_config))

    def _get_pdf_options_summary(self) -> str:
        if not self.generate_pdf.isChecked():
            return "Page options are disabled"

        if not self.pdf_draw_borders and not self.pdf_page_specs:
            return "No page options configured"

        return "Page options are set"

    def _refresh_pdf_options_summary(self):
        self.pdf_options_summary_label.setText(self._get_pdf_options_summary())

    def _set_processing_state(self, active: bool, aborting: bool = False):
        self.processing_active = active
        self.process_wavelog_button.setVisible(not active)
        self.process_adif_button.setVisible(not active)
        self.abort_processing_button.setVisible(active)
        self.abort_processing_button.setEnabled(active and not aborting)
        self.abort_processing_button.setText("Aborting..." if aborting else "Abort Processing")
        self._set_processing_buttons_enabled(not active)

    def _select_adif_source_file(self, suggested_path: str = '') -> str:
        start_path = str(suggested_path or '').strip()
        if start_path:
            path_obj = Path(start_path)
            if path_obj.exists() and path_obj.is_file():
                start_path = str(path_obj)
            else:
                start_path = str(Path.home())
        else:
            start_path = str(Path.home())

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select ADIF Source File",
            start_path,
            "ADIF Files (*.adi *.adif);;All Files (*)"
        )
        return str(file_path or '').strip()

    def _show_station_list_message(self, *lines: str):
        self.station_list.clear()
        self.station_list.setWordWrap(True)
        for line in (" ",) + lines:
            info_item = QListWidgetItem(line)
            info_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.station_list.addItem(info_item)

    def _set_station_controls_for_adif(self):
        self._show_station_list_message("Available only for Wavelog")
        self.all_stations_check.setChecked(True)
        self.all_stations_check.setEnabled(False)
        self.station_list.setEnabled(False)
        self.stations_loaded = False

    def _set_station_controls_for_wavelog(self):
        self.all_stations_check.setEnabled(True)

    def set_config(self, config):
        self.current_config = config
        has_wavelog_config = self._has_wavelog_config(config)
        self.refresh_station_btn.setEnabled(has_wavelog_config)
        self._set_processing_buttons_enabled(not self.processing_active and not self.mark_sent_active)

        if not has_wavelog_config:
            self._set_station_controls_for_adif()
            return

        self._set_station_controls_for_wavelog()
        self.load_station_list(config)

    def load_station_list(self, config):
        if not self._has_wavelog_config(config):
            self._set_station_controls_for_adif()
            return
        self._set_station_controls_for_wavelog()
        logger.info("Loading station list from Wavelog...")
        self.stations_loaded = False
        self.all_stations_check.setChecked(True)
        self.station_list.setEnabled(False)
        self.refresh_station_btn.setEnabled(False)
        self._show_station_list_message("Loading stations from Wavelog")

        self.station_request_id += 1
        request_id = self.station_request_id
        wavelog_url = config['wavelog_url']
        api_key = config['api_key']

        def task(worker):
            processor = QSLProcessor({})
            processor.api_client = create_wavelog_api(wavelog_url, api_key)
            return processor.list_stations()

        self.start_background_task(
            task,
            lambda stations: self._on_stations_loaded(request_id, stations),
            lambda error: self._on_stations_failed(request_id, error),
        )

    def _on_stations_loaded(self, request_id: int, stations):
        if request_id != self.station_request_id:
            return
        self.refresh_station_btn.setEnabled(True)
        self.station_list.clear()
        logger.info(f"Retrieved {len(stations)} stations from Wavelog")
        for s in stations:
            label = f"[{s['station_callsign']}] - {s['station_profile_name']}"
            logger.info(f"Added station: {label}")
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, s['station_id'])
            self.station_list.addItem(item)
        self.station_list.setEnabled(not self.all_stations_check.isChecked())
        logger.info("Station list loaded successfully")
        self.stations_loaded = True

    def _on_stations_failed(self, request_id: int, error):
        if request_id != self.station_request_id:
            return
        logger.error(f"Failed to load station list: {error}")
        self.refresh_station_btn.setEnabled(True)
        self.all_stations_check.setChecked(True)
        self.station_list.setEnabled(False)
        self.stations_loaded = False
        if isinstance(error, WavelogAuthError):
            self._show_station_list_message(
                "Missing Wavelog permissions",
                str(error),
                "Check the key with Test Key in Edit Settings",
            )
        else:
            self._show_station_list_message("Cannot load stations from Wavelog", str(error))

    def show_wavelog_permission_error(self, context: str, error_message: str):
        QMessageBox.warning(
            self,
            "Wavelog Permission Error",
            f"{context}\n\n{error_message}\n\n"
            "Open Edit Settings and use API Key Help or Test Key to check the required permissions."
        )
    def on_refresh_station_list(self):
        if self._has_wavelog_config(self.current_config):
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

        quick_range_layout = QHBoxLayout()
        self.select_range_btn = QPushButton("Select range...")
        self.select_range_btn.clicked.connect(self.open_select_range_dialog)
        self.select_range_btn.setMaximumWidth(150)
        quick_range_layout.addWidget(self.select_range_btn)
        quick_range_layout.addStretch()
        date_layout.addLayout(quick_range_layout)

        date_group.setLayout(date_layout)
        date_group.setMinimumWidth(210)
        date_group.setMaximumWidth(260)

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

        pdf_options_row = QHBoxLayout()
        self.pdf_options_button = QPushButton("PDF Options...")
        self.pdf_options_button.clicked.connect(self.open_pdf_options_dialog)
        pdf_options_row.addWidget(self.pdf_options_button)
        self.pdf_options_summary_label = QLabel()
        self.pdf_options_summary_label.setWordWrap(True)
        pdf_options_row.addWidget(self.pdf_options_summary_label, 1)
        output_layout.addLayout(pdf_options_row)

        self.include_direct_when_no_bureau = QCheckBox("Include direct when no bureau is found")
        self.include_direct_when_no_bureau.setChecked(False)
        output_layout.addWidget(self.include_direct_when_no_bureau)

        output_group.setLayout(output_layout)

        options_layout = QHBoxLayout()
        options_layout.addWidget(date_group, 1)
        options_layout.addWidget(output_group, 2)
        layout.addLayout(options_layout)

        process_buttons_layout = QHBoxLayout()
        self.process_wavelog_button = QPushButton("Process with Wavelog")
        self.process_wavelog_button.setMinimumHeight(40)
        self.process_wavelog_button.clicked.connect(self.start_wavelog_processing)
        process_buttons_layout.addWidget(self.process_wavelog_button)
        self.process_adif_button = QPushButton("Process with ADIF")
        self.process_adif_button.setMinimumHeight(40)
        self.process_adif_button.clicked.connect(self.start_adif_processing)
        process_buttons_layout.addWidget(self.process_adif_button)
        self.abort_processing_button = QPushButton("Abort Processing")
        self.abort_processing_button.setMinimumHeight(40)
        self.abort_processing_button.clicked.connect(self.abort_processing)
        self.abort_processing_button.setVisible(False)
        process_buttons_layout.addWidget(self.abort_processing_button)
        self.mark_sent_button = QPushButton("Mark as Sent in Wavelog")
        self.mark_sent_button.setMinimumHeight(40)
        self.mark_sent_button.clicked.connect(self.start_mark_as_sent)
        self.mark_sent_button.setEnabled(False)
        process_buttons_layout.addWidget(self.mark_sent_button)
        layout.addLayout(process_buttons_layout)

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
        self._refresh_pdf_options_summary()

    def on_date_filter_toggled(self):
        enabled = self.use_date_filter.isChecked()
        self.from_date_input.setEnabled(enabled)
        self.to_date_input.setEnabled(enabled)
        self.select_range_btn.setEnabled(enabled)

    def set_last_days_range(self, days: int):
        if days <= 0:
            return
        self.use_date_filter.setChecked(True)
        end_date = QDate.currentDate()
        start_date = end_date.addDays(-(days - 1))
        self.from_date_input.setDate(start_date)
        self.to_date_input.setDate(end_date)

    def set_last_full_months_range(self, months: int):
        if months <= 0:
            return
        self.use_date_filter.setChecked(True)
        today = QDate.currentDate()
        first_day_this_month = QDate(today.year(), today.month(), 1)
        end_date = first_day_this_month.addDays(-1)
        start_date = QDate(end_date.year(), end_date.month(), 1).addMonths(-(months - 1))
        self.from_date_input.setDate(start_date)
        self.to_date_input.setDate(end_date)

    def set_this_month_range(self):
        self.use_date_filter.setChecked(True)
        today = QDate.currentDate()
        start_date = QDate(today.year(), today.month(), 1)
        self.from_date_input.setDate(start_date)
        self.to_date_input.setDate(today)

    def set_this_year_range(self):
        self.use_date_filter.setChecked(True)
        today = QDate.currentDate()
        start_date = QDate(today.year(), 1, 1)
        self.from_date_input.setDate(start_date)
        self.to_date_input.setDate(today)

    def open_select_range_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Date Range Preset")
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.addWidget(QLabel("Choose a date range preset:"))

        days_radio = QRadioButton("Last")
        days_radio.setChecked(True)
        days_spin = QSpinBox()
        days_spin.setRange(1, 10000)
        days_spin.setValue(14)
        days_label = QLabel("days")
        days_layout = QHBoxLayout()
        days_layout.addWidget(days_radio)
        days_layout.addWidget(days_spin)
        days_layout.addWidget(days_label)
        days_layout.addStretch()
        dialog_layout.addLayout(days_layout)

        months_radio = QRadioButton("Last")
        months_spin = QSpinBox()
        months_spin.setRange(1, 120)
        months_spin.setValue(3)
        months_label = QLabel("full months")
        months_layout = QHBoxLayout()
        months_layout.addWidget(months_radio)
        months_layout.addWidget(months_spin)
        months_layout.addWidget(months_label)
        months_layout.addStretch()
        dialog_layout.addLayout(months_layout)

        this_month_radio = QRadioButton("Current month (from day 1 to today)")
        dialog_layout.addWidget(this_month_radio)

        this_year_radio = QRadioButton("Current year (from Jan 1 to today)")
        dialog_layout.addWidget(this_year_radio)

        days_spin.valueChanged.connect(lambda _: days_radio.setChecked(True))
        months_spin.valueChanged.connect(lambda _: months_radio.setChecked(True))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Apply")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Close")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        dialog_layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        if days_radio.isChecked():
            self.set_last_days_range(days_spin.value())
        elif months_radio.isChecked():
            self.set_last_full_months_range(months_spin.value())
        elif this_month_radio.isChecked():
            self.set_this_month_range()
        else:
            self.set_this_year_range()

    def on_generate_pdf_toggled(self):
        enabled = self.generate_pdf.isChecked()
        self.output_pdf_input.setEnabled(enabled)
        self.browse_pdf_btn.setEnabled(enabled)
        self.pdf_options_button.setEnabled(enabled)
        self._refresh_pdf_options_summary()

    def open_pdf_options_dialog(self):
        dialog = PdfOptionsDialog(self.pdf_draw_borders, self.pdf_page_options_text, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.pdf_page_specs = dialog.get_page_specs()
        except ValueError as e:
            QMessageBox.warning(self, "PDF Page Options Error", str(e))
            return
        self.pdf_draw_borders = dialog.get_draw_borders()
        self.pdf_page_options_text = dialog.get_page_options_text()
        self._refresh_pdf_options_summary()

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
        self.start_wavelog_processing()

    def start_wavelog_processing(self):
        self._start_processing('wavelog')

    def start_adif_processing(self):
        self._start_processing('adif_file')

    def _set_mark_sent_state(self, active: bool, text: str = "Mark as Sent in Wavelog", cancellable: bool = False):
        self.mark_sent_active = active
        self.mark_sent_button.setText(text)
        self._set_processing_buttons_enabled(not active)
        self.mark_sent_button.setEnabled(not active or cancellable)
        if not active:
            self.mark_sent_worker = None

    def _select_mark_sent_file(self) -> str:
        suggested_path = Path(self.output_adif_input.text().strip() or str(Path.home()))
        start_path = str(suggested_path) if suggested_path.is_file() else str(suggested_path.parent if suggested_path.parent.exists() else Path.home())
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select QSLMaster Output ADIF File",
            start_path,
            "ADIF Files (*.adi *.adif);;All Files (*)"
        )
        return str(file_path or '').strip()

    def start_mark_as_sent(self):
        if self.mark_sent_active and self.mark_sent_worker is not None:
            self.mark_sent_worker.request_stop()
            self.mark_sent_button.setEnabled(False)
            self.mark_sent_button.setText("Cancelling")
            self.on_log('WARNING', "Mark as sent cancel requested by user")
            return
        if self.processing_active or self.mark_sent_active:
            return
        if not self._has_wavelog_config(self.current_config):
            QMessageBox.warning(self, "Mark as Sent", "Wavelog URL and API key are required. Configure them in Edit Settings.")
            return

        adif_path = self._select_mark_sent_file()
        if not adif_path:
            return

        config_to_use = dict(self.current_config)
        config_to_use['source'] = 'wavelog'
        self.log_output.clear()
        self.progress_bar.setValue(0)
        self._set_mark_sent_state(True, "Matching QSOs")

        def task(worker):
            processor = QSLProcessor(
                config_to_use,
                progress_callback=worker.progress.emit,
                log_callback=worker.log.emit,
                progress_value_callback=worker.progress_value.emit,
            )
            return processor, processor.plan_mark_as_sent_from_adif(adif_path)

        self.start_background_task(
            task,
            lambda result: self._on_mark_sent_planned(result, adif_path),
            self._on_mark_sent_failed,
            on_progress=self.on_progress,
            on_progress_value=self.on_progress_value,
            on_log=self.on_log,
        )

    def _on_mark_sent_planned(self, result, adif_path: str):
        processor, plan = result
        if not plan.matched:
            self._set_mark_sent_state(False)
            QMessageBox.information(
                self,
                "Mark as Sent",
                f"No QSOs from the ADIF file were matched in Wavelog.\n\n"
                f"Not found: {len(plan.not_found)}\nAmbiguous: {len(plan.ambiguous)}\n\n"
                "Details are in the processing log."
            )
            return

        dialog = MarkSentDialog(plan, adif_path, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self._set_mark_sent_state(False)
            self.on_log('INFO', "Mark as sent cancelled by user")
            return

        sent_date = dialog.get_sent_date().isoformat()
        for match in plan.matched:
            match.fields['qslsdate'] = sent_date

        self._set_mark_sent_state(True, "Cancel Marking", cancellable=True)

        def task(worker):
            processor.progress_callback = worker.progress.emit
            processor.log_callback = worker.log.emit
            processor.progress_value_callback = worker.progress_value.emit
            return processor.apply_mark_as_sent(plan, should_stop=worker.should_stop)

        self.mark_sent_worker = self.start_background_task(
            task,
            lambda mark_result: self._on_mark_sent_done(mark_result, len(plan.matched)),
            self._on_mark_sent_failed,
            on_progress=self.on_progress,
            on_progress_value=self.on_progress_value,
            on_log=self.on_log,
        )

    def _on_mark_sent_done(self, result, total: int):
        self._set_mark_sent_state(False)
        message = f"Marked {result.updated} of {total} QSO(s) as sent in Wavelog."
        if result.updated + len(result.failed) < total:
            message += "\n\nCancelled before all QSOs were marked. Running Mark as Sent again with the same file is safe."
        if result.failed:
            message += f"\n\nFailed: {len(result.failed)}. Details are in the processing log."
            QMessageBox.warning(self, "Mark as Sent", message)
        else:
            QMessageBox.information(self, "Mark as Sent", message)

    def _on_mark_sent_failed(self, error):
        self._set_mark_sent_state(False)
        self.on_log('ERROR', f"Mark as sent failed: {error}")
        if isinstance(error, WavelogAuthError):
            self.show_wavelog_permission_error("Cannot mark QSOs as sent in Wavelog.", str(error))
        else:
            QMessageBox.critical(self, "Mark as Sent", f"Mark as sent failed:\n{error}")

    def _start_processing(self, source: str):
        if self.processing_active:
            return

        if not self.current_config:
            QMessageBox.warning(self, "Error", "No configuration loaded")
            return

        config_to_use = self.current_config.copy()
        source = self._normalize_source(source)
        config_to_use['source'] = source

        if source == 'wavelog':
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
        else:
            adif_path = self._select_adif_source_file(config_to_use.get('adif_file_path', ''))
            if not adif_path:
                return
            adif_file = Path(adif_path)
            if not adif_file.exists() or not adif_file.is_file():
                QMessageBox.warning(
                    self,
                    "Configuration Error",
                    f"ADIF file does not exist: {adif_path}"
                )
                return
            config_to_use['adif_file_path'] = str(adif_file)

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
        if source != 'wavelog' or self.all_stations_check.isChecked():
            selected_stations = ['all']
        else:
            for i in range(self.station_list.count()):
                item = self.station_list.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    selected_stations.append(item.data(Qt.ItemDataRole.UserRole))
        station_selector = selected_stations if selected_stations else None

        self.processor_worker = ProcessorWorker(
            config_to_use,
            from_date=from_date,
            to_date=to_date,
            modes=modes,
            output_adif=output_adif,
            generate_pdf=output_pdf,
            pdf_page_specs=self.pdf_page_specs,
            debug_labels=self.pdf_draw_borders,
            station_selector=station_selector,
            include_direct_when_no_bureau=self.include_direct_when_no_bureau.isChecked(),
        )

        self.processor_worker.signals.progress.connect(self.on_progress)
        self.processor_worker.signals.progress_value.connect(self.on_progress_value)
        self.processor_worker.signals.log.connect(self.on_log)
        self.processor_worker.signals.finished.connect(self.on_finished)
        self.processor_worker.signals.error.connect(self.on_error)
        self.processor_worker.signals.cancelled.connect(self.on_cancelled)

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.log_output.clear()
        self.qrz_error_count = 0
        self.pzk_error_count = 0
        self.qrz_disabled = False
        self.pzk_disabled = False

        self._set_processing_state(True)
        self.processor_worker.start()

    def abort_processing(self):
        if not self.processor_worker or not self.processing_active:
            return
        self.on_log('WARNING', 'Abort requested by user')
        self._set_processing_state(True, aborting=True)
        self.processor_worker.stop()

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
        self._set_processing_state(False)
        self.processor_worker = None

        if result['success']:
            stats_text = "Processing completed successfully!\n\n"
            stats_text += f"Total QSOs to send: {result['stats'].get('total_to_send', 0)}\n"

            callsign_filter_stats = result['stats'].get('callsign_filter')
            ignored_dxcc_stats = result['stats'].get('ignored_dxcc')
            already_sent_stats = result['stats'].get('already_sent')
            delivery_method_stats = result['stats'].get('delivery_methods')

            if isinstance(delivery_method_stats, dict):
                stats_text += f"Delivery methods: bureau: {int(delivery_method_stats.get('bureau', 0) or 0)}, direct: {int(delivery_method_stats.get('direct', 0) or 0)}\n"

            for country, stats in result['stats'].items():
                if country in {'total_to_send', 'delivery_methods', 'callsign_filter', 'ignored_dxcc', 'already_sent', 'can_mark_as_sent'}:
                    continue
                if isinstance(stats, dict):
                    stats_text += f"{country}: {stats.get('to_send', 0)}/{stats.get('total', 0)} (bureau: {stats.get('bureau', 0)}, direct: {stats.get('direct', 0)})\n"

            if isinstance(callsign_filter_stats, dict):
                mode = str(callsign_filter_stats.get('mode', 'off') or 'off').strip().lower()
                mode_label = 'allow list' if mode == 'allow' else 'block list'
                skipped = int(callsign_filter_stats.get('skipped', 0) or 0)
                stats_text += f"Callsign filter ({mode_label}): {skipped}\n"

            if isinstance(ignored_dxcc_stats, dict):
                skipped = int(ignored_dxcc_stats.get('skipped', 0) or 0)
                stats_text += f"Ignored DXCC: {skipped}\n"

            if isinstance(already_sent_stats, dict):
                skipped = int(already_sent_stats.get('skipped', 0) or 0)
                stats_text += f"Already sent QSOs: {skipped}\n"

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

            if result['stats'].get('can_mark_as_sent') and result['stats'].get('total_to_send'):
                stats_text += "\nAfter sending the cards, use \"Mark as Sent in Wavelog\" with the output ADIF file.\n"

            QMessageBox.information(self, "Processing Complete", stats_text)
        elif result.get('permission_error'):
            self.show_wavelog_permission_error("Cannot download the log from Wavelog.", str(result.get('error')))
        else:
            QMessageBox.critical(self, "Processing Failed", f"Error: {result.get('error')}")

    @pyqtSlot(str)
    def on_error(self, error_message: str):
        self.progress_bar.setVisible(False)
        self._set_processing_state(False)
        self.processor_worker = None
        QMessageBox.critical(self, "Processing Error", f"An error occurred: {error_message}")

    @pyqtSlot(str)
    def on_cancelled(self, message: str):
        self.progress_bar.setVisible(False)
        self._set_processing_state(False)
        self.processor_worker = None
        QMessageBox.information(self, "Processing Aborted", message)
