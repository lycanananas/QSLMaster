import logging
from typing import Callable, Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QComboBox, QMessageBox, QFileDialog,
    QListWidget, QListWidgetItem, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QColor, QPainter, QPen

from qslmaster_gui.utils.config_manager import (
    list_all_configs, get_config, create_config, update_config, delete_config,
    get_current_config_id, set_current_config_id, _save_logo_file, _delete_logo_file
)
from qslmaster_cli.qslmaster_core import QSLProcessor

logger = logging.getLogger(__name__)


class ConfigDialog(QDialog):
    _dxcc_entities_cache = None

    def __init__(
        self,
        parent=None,
        on_config_deleted: Optional[Callable[[str], None]] = None,
        on_config_created: Optional[Callable[[str], None]] = None
    ):
        super().__init__(parent)
        self.setWindowTitle("QSL Configuration")
        self.setGeometry(180, 120, 980, 680)
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

        content_layout = QHBoxLayout()

        left_column = QVBoxLayout()

        self.wavelog_group = QGroupBox("Wavelog Configuration")
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
        
        wavelog_note = QLabel("Optional! Required only when processing from Wavelog.")
        wavelog_note.setWordWrap(True)
        wavelog_layout.addWidget(wavelog_note)

        self.wavelog_group.setLayout(wavelog_layout)
        self.wavelog_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        left_column.addWidget(self.wavelog_group)

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

        qrz_note = QLabel(
            "QRZ XML API access (premium subscription) is required for bureau lookups. "
            "Without premium access, lookup errors are treated as non-fatal and processing continues."
        )
        qrz_note.setWordWrap(True)
        qrz_layout.addWidget(qrz_note)

        qrz_group.setLayout(qrz_layout)
        qrz_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        left_column.addWidget(qrz_group)

        logo_group = QGroupBox("QSL Logo (Optional)")
        logo_layout = QVBoxLayout()
        
        logo_layout.addWidget(QLabel("Logo File:"))
        self.logo_input = QLineEdit()
        self.logo_input.setPlaceholderText("No logo selected")
        self.logo_input.setReadOnly(True)
        logo_layout.addWidget(self.logo_input)
        
        logo_btn_layout = QHBoxLayout()
        logo_browse_btn = QPushButton("Browse...")
        logo_browse_btn.clicked.connect(self.browse_logo_file)
        logo_btn_layout.addWidget(logo_browse_btn)
        
        logo_remove_btn = QPushButton("Remove")
        logo_remove_btn.clicked.connect(self.remove_logo)
        logo_btn_layout.addWidget(logo_remove_btn)
        logo_layout.addLayout(logo_btn_layout)

        logo_layout.addWidget(QLabel("Logo Preview:"))
        self.logo_preview = QLabel()
        self.logo_preview.setFixedSize(220, 140)
        self.logo_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_preview.setStyleSheet("border: 1px solid #666;")
        self.update_logo_preview('')
        logo_layout.addWidget(self.logo_preview)
        
        logo_group.setLayout(logo_layout)
        logo_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        left_column.addWidget(logo_group)
        left_column.addStretch()

        dxcc_group = QGroupBox("Ignored DXCC (Optional)")
        dxcc_layout = QVBoxLayout()

        dxcc_layout.addWidget(QLabel("Select DXCC entities to ignore when generating QSLs:"))
        self.dxcc_search_input = QLineEdit()
        self.dxcc_search_input.setPlaceholderText("Search by DXCC name or ID...")
        self.dxcc_search_input.textChanged.connect(self.on_dxcc_search_changed)
        dxcc_layout.addWidget(self.dxcc_search_input)

        self.dxcc_list = QListWidget()
        self.dxcc_list.setMinimumHeight(220)
        dxcc_layout.addWidget(self.dxcc_list)

        dxcc_buttons_layout = QHBoxLayout()
        dxcc_reload_btn = QPushButton("Reload DXCC List")
        dxcc_reload_btn.clicked.connect(lambda: self.load_dxcc_options(force_reload=True))
        dxcc_buttons_layout.addWidget(dxcc_reload_btn)

        dxcc_clear_btn = QPushButton("Clear Selection")
        dxcc_clear_btn.clicked.connect(self.clear_dxcc_selection)
        dxcc_buttons_layout.addWidget(dxcc_clear_btn)
        dxcc_layout.addLayout(dxcc_buttons_layout)

        dxcc_group.setLayout(dxcc_layout)

        right_column = QVBoxLayout()
        right_column.addWidget(dxcc_group)
        right_column.addStretch()

        content_layout.addLayout(left_column, 1)
        content_layout.addLayout(right_column, 1)
        layout.addLayout(content_layout)

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
        self.load_dxcc_options()

    def load_dxcc_options(self, force_reload: bool = False):
        selected_ids = set(self.get_selected_dxcc_ids())
        self.dxcc_list.clear()

        try:
            if force_reload or ConfigDialog._dxcc_entities_cache is None:
                ConfigDialog._dxcc_entities_cache = QSLProcessor.list_all_dxcc_entities()
            entities = ConfigDialog._dxcc_entities_cache
        except Exception as e:
            logger.error(f"Failed to load DXCC list: {e}")
            QMessageBox.warning(self, "DXCC List Error", f"Could not load DXCC list: {e}")
            return

        for entity in entities:
            dxcc_id = int(entity.get('id'))
            name = str(entity.get('name', '')).strip()
            text = f"{name} ({dxcc_id})"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, dxcc_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            if dxcc_id in selected_ids:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)
            self.dxcc_list.addItem(item)

        self.on_dxcc_search_changed(self.dxcc_search_input.text())

    def on_dxcc_search_changed(self, text: str):
        query = str(text or '').strip().lower()
        for i in range(self.dxcc_list.count()):
            item = self.dxcc_list.item(i)
            dxcc_id = item.data(Qt.ItemDataRole.UserRole)
            item_text = item.text().lower()
            if not query:
                item.setHidden(False)
                continue
            id_text = str(dxcc_id or '')
            item.setHidden(query not in item_text and query not in id_text)

    def update_logo_preview(self, logo_path: str):
        canvas = self.build_logo_preview_canvas()
        path = str(logo_path or '').strip()
        if not path:
            painter = QPainter(canvas)
            painter.setPen(QPen(QColor(70, 70, 70)))
            painter.drawText(canvas.rect(), Qt.AlignmentFlag.AlignCenter, 'No logo')
            painter.end()
            self.logo_preview.setPixmap(canvas)
            return

        pixmap = QPixmap(path)
        if pixmap.isNull():
            painter = QPainter(canvas)
            painter.setPen(QPen(QColor(160, 40, 40)))
            painter.drawText(canvas.rect(), Qt.AlignmentFlag.AlignCenter, 'Preview unavailable')
            painter.end()
            self.logo_preview.setPixmap(canvas)
            return

        scaled = pixmap.scaled(
            max(1, self.logo_preview.width() - 8),
            max(1, self.logo_preview.height() - 8),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter = QPainter(canvas)
        x_pos = (canvas.width() - scaled.width()) // 2
        y_pos = (canvas.height() - scaled.height()) // 2
        painter.drawPixmap(x_pos, y_pos, scaled)
        painter.end()
        self.logo_preview.setPixmap(canvas)

    def build_logo_preview_canvas(self) -> QPixmap:
        width = max(1, self.logo_preview.width() - 2)
        height = max(1, self.logo_preview.height() - 2)
        canvas = QPixmap(width, height)

        tile_size = 16
        half = tile_size // 2
        light = QColor(210, 210, 210)
        dark = QColor(170, 170, 170)

        painter = QPainter(canvas)
        y_pos = 0
        while y_pos < height:
            x_pos = 0
            while x_pos < width:
                painter.fillRect(x_pos, y_pos, half, half, dark)
                painter.fillRect(x_pos + half, y_pos, half, half, light)
                painter.fillRect(x_pos, y_pos + half, half, half, light)
                painter.fillRect(x_pos + half, y_pos + half, half, half, dark)
                x_pos += tile_size
            y_pos += tile_size
        painter.end()
        return canvas

    def clear_dxcc_selection(self):
        for i in range(self.dxcc_list.count()):
            item = self.dxcc_list.item(i)
            item.setCheckState(Qt.CheckState.Unchecked)

    def get_selected_dxcc_ids(self):
        selected = []
        for i in range(self.dxcc_list.count()):
            item = self.dxcc_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                value = item.data(Qt.ItemDataRole.UserRole)
                if value is not None:
                    selected.append(int(value))
        return sorted(set(selected))

    def set_selected_dxcc_ids(self, dxcc_ids):
        selected = set()
        for value in dxcc_ids or []:
            try:
                selected.add(int(str(value).strip()))
            except Exception:
                continue

        for i in range(self.dxcc_list.count()):
            item = self.dxcc_list.item(i)
            value = item.data(Qt.ItemDataRole.UserRole)
            if value in selected:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)

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
            self.wavelog_url_input.clear()
            self.api_key_input.clear()
            self.qrz_username_input.clear()
            self.qrz_password_input.clear()
            self.logo_input.clear()
            self.update_logo_preview('')
            self.clear_dxcc_selection()
            return

        config = get_config(config_id)
        if config:
            self.wavelog_url_input.setText(config.get('wavelog_url', ''))
            self.api_key_input.setText(config.get('api_key', ''))
            self.qrz_username_input.setText(config.get('qrz_username', ''))
            self.qrz_password_input.setText(config.get('qrz_password', ''))
            self.set_selected_dxcc_ids(config.get('ignored_dxcc', []))
            
            logo_path = config.get('logo_path', '')
            if logo_path:
                self.logo_input.setText(logo_path)
                self.update_logo_preview(logo_path)
            else:
                self.logo_input.clear()
                self.update_logo_preview('')

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
            self.update_logo_preview(file_path)
            logger.info(f"Logo input set to: {self.logo_input.text()}")
    
    def remove_logo(self):
        config_id = self.config_combo.currentData()
        if config_id:
            _delete_logo_file(config_id)
            self.logo_input.clear()
            self.update_logo_preview('')

    def save_config(self):
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
                self.qrz_password_input.text() if self.qrz_password_input.text() else None,
                self.get_selected_dxcc_ids(),
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
            self.qrz_password_input.text() if self.qrz_password_input.text() else None,
            self.get_selected_dxcc_ids(),
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
