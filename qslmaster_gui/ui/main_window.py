import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap

from qslmaster_gui.dialogs import ConfigDialog
from qslmaster_gui.widgets import ProcessingTab
from qslmaster_gui.utils.config_manager import (
    list_all_configs, get_config, get_current_config_id, set_current_config_id
)

logger = logging.getLogger(__name__)



class QSLMasterMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = None
        self.init_ui()
        self.load_config()

    def init_ui(self):
        self.setWindowTitle("QSLMaster")
        self.setObjectName("QSLMaster")
        
        icon_path = Path(__file__).parent.parent / 'resources' / 'icon.png'
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        
        self.setGeometry(100, 100, 900, 700)

        central_widget = QWidget()
        layout = QVBoxLayout()

        top_layout = QHBoxLayout()

        config_block = QVBoxLayout()
        config_block.addWidget(QLabel("Configuration:"))

        config_row = QHBoxLayout()
        self.config_combo = QComboBox()
        self.config_combo.setMinimumWidth(320)
        self.config_combo.currentIndexChanged.connect(self.on_config_changed)
        config_row.addWidget(self.config_combo)

        settings_btn = QPushButton("Edit Settings")
        settings_btn.clicked.connect(self.open_settings)
        config_row.addWidget(settings_btn)

        config_block.addLayout(config_row)
        top_layout.addLayout(config_block)

        top_layout.addStretch()
        logo_label = QLabel()
        logo_pixmap = QPixmap(str(icon_path))
        if not logo_pixmap.isNull():
            logo_label.setPixmap(logo_pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        top_layout.addWidget(logo_label)
        layout.addLayout(top_layout)

        self.processing_tab = ProcessingTab()
        layout.addWidget(self.processing_tab)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.statusBar().showMessage("Ready")

    def load_config(self):
        try:
            configs = list_all_configs()

            if not configs:
                self.statusBar().showMessage(
                    "No configurations found. Click 'Edit Settings' to create one"
                )
                return

            self.refresh_and_update_combo()

            if not self.processing_tab.current_config:
                current_id = get_current_config_id()
                if current_id:
                    config = get_config(current_id)
                    if config:
                        self.processing_tab.current_config = config
                else:
                    config = get_config(configs[0]['id'])
                    if config:
                        self.processing_tab.current_config = config
                        set_current_config_id(configs[0]['id'])

            self.statusBar().showMessage("Configuration loaded")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            self.statusBar().showMessage(f"Error loading configuration: {e}")

    def open_settings(self):
        dialog = ConfigDialog(
            self,
            on_config_deleted=self._on_config_deleted,
            on_config_created=self._on_config_created
        )
        dialog.exec()
        self.refresh_and_update_combo()

    def _on_config_deleted(self, deleted_config_id: str):
        if (
            self.processing_tab.current_config and
            self.processing_tab.current_config.get('id') == deleted_config_id
        ):
            self.processing_tab.current_config = None
            self.statusBar().showMessage(
                "Configuration deleted. Please select another configuration."
            )

    def _on_config_created(self, created_config_id: str):
        config = get_config(created_config_id)
        if config:
            self.processing_tab.current_config = config
            self.statusBar().showMessage(
                f"Configuration created: {config.get('name', created_config_id[:8])}"
            )

    def on_config_changed(self):
        config_id = self.config_combo.currentData()
        if config_id:
            config = get_config(config_id)
            if config:
                self.processing_tab.current_config = config
                set_current_config_id(config_id)
                self.statusBar().showMessage(f"Configuration: {self.config_combo.currentText()}")

    def refresh_and_update_combo(self):
        configs = list_all_configs()
        self.config_combo.currentIndexChanged.disconnect()
        self.config_combo.clear()

        for cfg in configs:
            self.config_combo.addItem(
                cfg.get('name', f"Config {cfg['id'][:8]}"),
                cfg['id']
            )

        current_id = get_current_config_id()
        if current_id:
            idx = self.config_combo.findData(current_id)
            if idx >= 0:
                self.config_combo.setCurrentIndex(idx)

        self.config_combo.currentIndexChanged.connect(self.on_config_changed)

    def closeEvent(self, event):
        if (
            self.processing_tab.processor_worker and
            self.processing_tab.thread_pool.activeThreadCount() > 0
        ):
            self.processing_tab.thread_pool.waitForDone(5000)
        event.accept()

