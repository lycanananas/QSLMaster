import logging
from typing import Callable, Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QComboBox, QMessageBox, QFileDialog
)

from qslmaster_gui.utils.config_manager import (
    list_all_configs, get_config, create_config, update_config, delete_config,
    get_current_config_id, set_current_config_id, _save_logo_file, _delete_logo_file
)

logger = logging.getLogger(__name__)


class ConfigDialog(QDialog):
    def __init__(
        self,
        parent=None,
        on_config_deleted: Optional[Callable[[str], None]] = None,
        on_config_created: Optional[Callable[[str], None]] = None
    ):
        super().__init__(parent)
        self.setWindowTitle("QSL Configuration")
        self.setGeometry(200, 200, 500, 400)
        self.on_config_deleted = on_config_deleted
        self.on_config_created = on_config_created
        self.init_ui()
        self.load_configs()

    def init_ui(self):
        layout = QVBoxLayout()

        config_layout = QHBoxLayout()
        config_layout.addWidget(QLabel("Configuration:"))
        self.config_combo = QComboBox()
        config_layout.addWidget(self.config_combo)
        layout.addLayout(config_layout)

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

        logo_group = QGroupBox("QSL Logo (Optional)")
        logo_layout = QVBoxLayout()
        
        logo_layout.addWidget(QLabel("Logo File:"))
        self.logo_input = QLineEdit()
        self.logo_input.setPlaceholderText("No logo selected")
        logo_layout.addWidget(self.logo_input)
        
        logo_btn_layout = QHBoxLayout()
        logo_browse_btn = QPushButton("Browse...")
        logo_browse_btn.clicked.connect(self.browse_logo_file)
        logo_btn_layout.addWidget(logo_browse_btn)
        
        logo_remove_btn = QPushButton("Remove")
        logo_remove_btn.clicked.connect(self.remove_logo)
        logo_btn_layout.addWidget(logo_remove_btn)
        logo_layout.addLayout(logo_btn_layout)
        
        logo_group.setLayout(logo_layout)
        layout.addWidget(logo_group)

        button_layout = QHBoxLayout()

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_config)
        button_layout.addWidget(save_btn)

        save_as_btn = QPushButton("Save As New...")
        save_as_btn.clicked.connect(self.save_config_as)
        button_layout.addWidget(save_as_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self.delete_config)
        button_layout.addWidget(delete_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def load_configs(self):
        configs = list_all_configs()
        self.config_combo.clear()

        for cfg in configs:
            self.config_combo.addItem(cfg.get('name', f"Config {cfg['id'][:8]}"), cfg['id'])

        current_id = get_current_config_id()
        if current_id:
            idx = self.config_combo.findData(current_id)
            if idx >= 0:
                self.config_combo.setCurrentIndex(idx)

        self.config_combo.currentIndexChanged.connect(self.load_current_config)

        if configs:
            self.load_current_config()

    def load_current_config(self):
        config_id = self.config_combo.currentData()
        if not config_id:
            self.logo_input.clear()
            return

        config = get_config(config_id)
        if config:
            self.wavelog_url_input.setText(config.get('wavelog_url', ''))
            self.api_key_input.setText(config.get('api_key', ''))
            self.qrz_username_input.setText(config.get('qrz_username', ''))
            self.qrz_password_input.setText(config.get('qrz_password', ''))
            
            logo_path = config.get('logo_path', '')
            if logo_path:
                self.logo_input.setText(logo_path)
            else:
                self.logo_input.clear()

    def browse_logo_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select QSL Logo",
            str(Path.home()),
            "Image Files (*.png *.jpg *.jpeg);;All Files (*)"
        )
        logger.info(f"QFileDialog returned: {file_path}")
        if file_path:
            self.logo_input.setText(file_path)
            logger.info(f"Logo input set to: {self.logo_input.text()}")
    
    def remove_logo(self):
        config_id = self.config_combo.currentData()
        if config_id:
            _delete_logo_file(config_id)
            self.logo_input.clear()

    def save_config(self):
        if not self.wavelog_url_input.text():
            QMessageBox.warning(self, "Validation Error", "Wavelog URL is required")
            return

        if not self.api_key_input.text():
            QMessageBox.warning(self, "Validation Error", "API Key is required")
            return

        config_id = self.config_combo.currentData()
        if config_id:
            reply = QMessageBox.question(
                self,
                "Confirm Save",
                f"Update configuration '{self.config_combo.currentText()}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            if update_config(
                config_id,
                self.config_combo.currentText(),
                self.wavelog_url_input.text(),
                self.qrz_username_input.text(),
                self.api_key_input.text(),
                self.qrz_password_input.text() if self.qrz_password_input.text() else None
            ):
                logo_file = self.logo_input.text().strip()
                if logo_file:
                    if not _save_logo_file(config_id, logo_file):
                        QMessageBox.warning(self, "Warning", "Configuration saved but logo upload failed")
                        return
                QMessageBox.information(self, "Success", "Configuration saved")
            else:
                QMessageBox.critical(self, "Error", "Failed to save configuration")
        else:
            self.save_config_as()

    def save_config_as(self):
        if not self.wavelog_url_input.text():
            QMessageBox.warning(self, "Validation Error", "Wavelog URL is required")
            return

        if not self.api_key_input.text():
            QMessageBox.warning(self, "Validation Error", "API Key is required")
            return

        name_dialog = QDialog(self)
        name_dialog.setWindowTitle("New Configuration")
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Configuration name:"))
        name_input = QLineEdit()
        layout.addWidget(name_input)

        button_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        name_dialog.setLayout(layout)

        accepted = False
        name = ""

        def on_ok():
            nonlocal accepted, name
            name = name_input.text()
            if name:
                accepted = True
                name_dialog.accept()

        ok_btn.clicked.connect(on_ok)
        cancel_btn.clicked.connect(name_dialog.reject)

        name_dialog.exec()

        if not accepted or not name:
            return

        config_id = create_config(
            name,
            self.wavelog_url_input.text(),
            self.qrz_username_input.text(),
            self.api_key_input.text(),
            self.qrz_password_input.text() if self.qrz_password_input.text() else None
        )

        if config_id:
            logo_file = self.logo_input.text().strip()
            if logo_file:
                if not _save_logo_file(config_id, logo_file):
                    QMessageBox.warning(self, "Warning", "Configuration created but logo upload failed")
                    return
            
            self.load_configs()
            idx = self.config_combo.findData(config_id)
            if idx >= 0:
                self.config_combo.setCurrentIndex(idx)
            QMessageBox.information(self, "Success", f"Configuration '{name}' created")
            set_current_config_id(config_id)
            if self.on_config_created:
                self.on_config_created(config_id)
        else:
            QMessageBox.critical(self, "Error", "Failed to create configuration")

    def delete_config(self):
        config_id = self.config_combo.currentData()
        if not config_id:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete configuration '{self.config_combo.currentText()}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if delete_config(config_id):
                self.load_configs()
                QMessageBox.information(self, "Success", "Configuration deleted")
                if self.on_config_deleted:
                    self.on_config_deleted(config_id)
            else:
                QMessageBox.critical(self, "Error", "Failed to delete configuration")
