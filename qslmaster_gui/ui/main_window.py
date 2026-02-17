"""
Main GUI window for QSLMaster
"""
import logging
from typing import Optional
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QDateEdit, QCheckBox, QGroupBox, QTextEdit, QProgressBar,
    QFileDialog, QMessageBox, QComboBox, QSpinBox, QTabWidget, QStatusBar
)
from PyQt6.QtCore import Qt, QDate, QThreadPool, pyqtSlot
from PyQt6.QtGui import QFont, QIcon

from qslmaster_cli.config import load_config, validate_config, ConfigError
from qslmaster_gui.utils.config_manager import load_gui_config, save_gui_config, save_credentials
from qslmaster_gui.workers.processor_worker import ProcessorWorker


logger = logging.getLogger(__name__)


class ConfigTab(QWidget):
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_saved = None
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        wavelog_group = QGroupBox("Wavelog Configuration")
        wavelog_layout = QVBoxLayout()
        
        wavelog_layout.addWidget(QLabel("Wavelog URL:"))
        self.wavelog_url_input = QLineEdit()
        self.wavelog_url_input.setPlaceholderText("https://your-wavelog-instance.com")
        wavelog_layout.addWidget(self.wavelog_url_input)
        
        wavelog_layout.addWidget(QLabel("API Key:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("Your Wavelog API key")
        wavelog_layout.addWidget(self.api_key_input)
        
        wavelog_group.setLayout(wavelog_layout)
        layout.addWidget(wavelog_group)
        
        qrz_group = QGroupBox("QRZ.com Configuration (Optional)")
        qrz_layout = QVBoxLayout()
        
        qrz_layout.addWidget(QLabel("QRZ Username:"))
        self.qrz_username_input = QLineEdit()
        self.qrz_username_input.setPlaceholderText("Your QRZ username (optional)")
        qrz_layout.addWidget(self.qrz_username_input)
        
        qrz_layout.addWidget(QLabel("QRZ Password:"))
        self.qrz_password_input = QLineEdit()
        self.qrz_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.qrz_password_input.setPlaceholderText("Your QRZ password (optional)")
        qrz_layout.addWidget(self.qrz_password_input)
        
        qrz_group.setLayout(qrz_layout)
        layout.addWidget(qrz_group)
        
        save_button = QPushButton("Save Configuration")
        save_button.clicked.connect(self.save_config)
        layout.addWidget(save_button)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def load_config(self, config: dict):
        self.wavelog_url_input.setText(config.get('wavelog_url', ''))
        self.api_key_input.setText(config.get('api_key', ''))
        self.qrz_username_input.setText(config.get('qrz_username', ''))
        self.qrz_password_input.setText(config.get('qrz_password', ''))
    
    def save_config(self):
        if not self.wavelog_url_input.text():
            QMessageBox.warning(self, "Validation Error", "Wavelog URL is required")
            return
        
        if not self.api_key_input.text():
            QMessageBox.warning(self, "Validation Error", "API Key is required")
            return
        
        config = {
            'wavelog_url': self.wavelog_url_input.text(),
            'qrz_username': self.qrz_username_input.text(),
            'api_key': self.api_key_input.text(),
        }
        
        if save_gui_config(config):
            save_credentials(
                self.api_key_input.text(),
                self.qrz_password_input.text() if self.qrz_password_input.text() else None
            )
            QMessageBox.information(self, "Success", "Configuration saved successfully")
            if self.config_saved:
                self.config_saved()
        else:
            QMessageBox.critical(self, "Error", "Failed to save configuration")


class ProcessingTab(QWidget):
    
    def __init__(self, config_tab=None, parent=None):
        super().__init__(parent)
        self.config_tab = config_tab
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
        
        process_button = QPushButton("Download & Process QSOs")
        process_button.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        process_button.setMinimumHeight(40)
        process_button.clicked.connect(self.start_processing)
        layout.addWidget(process_button)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        layout.addWidget(QLabel("Processing Log:"))
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(200)
        layout.addWidget(self.log_output)
        
        layout.addStretch()
        self.setLayout(layout)
        
        self.on_date_filter_toggled()
    
    def on_date_filter_toggled(self):
        enabled = self.use_date_filter.isChecked()
        self.from_date_input.setEnabled(enabled)
        self.to_date_input.setEnabled(enabled)
    
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
        
        if not config_to_use.get('api_key') and self.config_tab:
            config_to_use['api_key'] = self.config_tab.api_key_input.text()
        
        if not config_to_use.get('api_key'):
            QMessageBox.warning(self, "Configuration Error", "API Key not found. Please configure it first")
            return
        
        if not config_to_use.get('wavelog_url'):
            wavelog_url = self.config_tab.wavelog_url_input.text() if self.config_tab else ''
            if wavelog_url:
                config_to_use['wavelog_url'] = wavelog_url
            else:
                QMessageBox.warning(self, "Configuration Error", "Wavelog URL not found. Please configure it first")
                return
        
        from_date = None
        to_date = None
        if self.use_date_filter.isChecked():
            from_date = self.from_date_input.date().toPyDate().strftime('%Y-%m-%d')
            to_date = self.to_date_input.date().toPyDate().strftime('%Y-%m-%d')
        
        output_adif = self.output_adif_input.text()
        output_pdf = self.output_pdf_input.text() if self.generate_pdf.isChecked() else None
        
        self.processor_worker = ProcessorWorker(
            config_to_use,
            from_date=from_date,
            to_date=to_date,
            output_adif=output_adif,
            generate_pdf=output_pdf,
            debug_labels=self.debug_labels.isChecked(),
        )
        
        self.processor_worker.signals.progress.connect(self.on_progress)
        self.processor_worker.signals.log.connect(self.on_log)
        self.processor_worker.signals.finished.connect(self.on_finished)
        self.processor_worker.signals.error.connect(self.on_error)
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.log_output.clear()
        
        self.thread_pool.start(self.processor_worker)
    
    @pyqtSlot(str)
    def on_progress(self, message: str):
        self.log_output.append(f"[PROGRESS] {message}")
    
    @pyqtSlot(str, str)
    def on_log(self, level: str, message: str):
        self.log_output.append(f"[{level}] {message}")
    
    @pyqtSlot(dict)
    def on_finished(self, result: dict):
        self.progress_bar.setVisible(False)
        
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
        QMessageBox.critical(self, "Processing Error", f"An error occurred: {error_message}")


class QSLMasterMainWindow(QMainWindow):
    
    def __init__(self):
        super().__init__()
        self.config = None
        self.init_ui()
        self.load_config()
    
    def init_ui(self):
        self.setWindowTitle("QSLMaster - QSL Label Generator")
        self.setGeometry(100, 100, 900, 700)
        
        central_widget = QWidget()
        layout = QVBoxLayout()
        
        self.tabs = QTabWidget()
        
        self.config_tab = ConfigTab()
        self.processing_tab = ProcessingTab(config_tab=self.config_tab)
        
        self.config_tab.config_saved = self.refresh_config
        
        self.tabs.addTab(self.config_tab, "Configuration")
        self.tabs.addTab(self.processing_tab, "Processing")
        
        layout.addWidget(self.tabs)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        
        self.statusBar().showMessage("Ready")
    
    def load_config(self):
        try:
            self.config = load_gui_config()
            self.config_tab.load_config(self.config)
            self.processing_tab.current_config = self.config
            self.statusBar().showMessage("Configuration loaded")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            self.statusBar().showMessage(f"Error loading configuration: {e}")
    
    def refresh_config(self):
        self.load_config()
    
    def closeEvent(self, event):
        if self.processing_tab.processor_worker and self.processing_tab.thread_pool.activeThreadCount() > 0:
            self.processing_tab.thread_pool.waitForDone(5000)
        event.accept()
