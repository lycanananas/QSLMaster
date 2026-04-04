from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget
)
from PyQt6.QtCore import Qt

from qslmaster_cli.pdf_labels import get_labels_per_page, normalize_pdf_page_specs


class PdfPageRuleRow(QWidget):
    def __init__(self, page_number: int, labels_per_page: int, offset: int = 0, skip_slots=None, parent=None):
        super().__init__(parent)
        self.labels_per_page = labels_per_page
        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(6)

        self.page_label = QLabel()
        self.page_label.setMinimumWidth(58)
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.layout.addWidget(self.page_label)

        self.offset_label = QLabel("Offset")
        self.offset_label.setMinimumWidth(44)
        self.layout.addWidget(self.offset_label)
        self.offset_input = QSpinBox()
        self.offset_input.setRange(0, labels_per_page)
        self.offset_input.setValue(int(offset))
        self.offset_input.setMinimumWidth(62)
        self.layout.addWidget(self.offset_input)

        self.skip_label = QLabel("Skip labels")
        self.skip_label.setMinimumWidth(72)
        self.layout.addWidget(self.skip_label)
        self.skip_slots_input = QLineEdit()
        self.skip_slots_input.setPlaceholderText("8,9")
        self.skip_slots_input.setText(','.join(str(value) for value in (skip_slots or [])))
        self.skip_slots_input.setMinimumWidth(120)
        self.layout.addWidget(self.skip_slots_input, 1)

        self.remove_button = QPushButton("Remove")
        self.remove_button.setMinimumWidth(82)
        self.layout.addWidget(self.remove_button)

        self.setLayout(self.layout)
        self.set_page_number(page_number)

    def set_page_number(self, page_number: int):
        self.page_label.setText(f"Page {page_number}")

    def to_line(self) -> str:
        skip_slots = self.skip_slots_input.text().strip()
        return f"{self.offset_input.value()}|{skip_slots}"

    def is_configured(self) -> bool:
        return self.offset_input.value() > 0 or bool(self.skip_slots_input.text().strip())


class PdfOptionsDialog(QDialog):
    def __init__(self, draw_borders: bool = False, page_options_text: str = '', parent=None):
        super().__init__(parent)
        self.setWindowTitle("Page Options")
        self.resize(720, 420)
        self.labels_per_page = get_labels_per_page()
        self.page_rows = []

        layout = QVBoxLayout()

        self.draw_borders_checkbox = QCheckBox("Draw red guide borders")
        self.draw_borders_checkbox.setChecked(draw_borders)
        layout.addWidget(self.draw_borders_checkbox)

        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Page setup:"))
        header_layout.addStretch()
        self.add_page_button = QPushButton("Add page")
        self.add_page_button.clicked.connect(self.add_page_row)
        header_layout.addWidget(self.add_page_button)
        layout.addLayout(header_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(8)
        self.rows_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.empty_state_label = QLabel("No pages added")
        self.empty_state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rows_layout.addWidget(self.empty_state_label)
        self.scroll_content.setLayout(self.rows_layout)
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area)

        note_label = QLabel(
            f"Offset means how many labels are already used at the start of the page. In Skip labels, enter label numbers that should stay empty, from 1 to {self.labels_per_page}, separated with commas. Labels are numbered from left to right, then row by row from top to bottom."
        )
        note_label.setWordWrap(True)
        layout.addWidget(note_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)
        self.load_page_rows(page_options_text)

    def load_page_rows(self, page_options_text: str):
        page_specs = normalize_pdf_page_specs(page_options_text.splitlines()) if page_options_text.strip() else []
        for page_spec in page_specs:
            self.add_page_row(page_spec.get('offset', 0), page_spec.get('skip_slots', []))
        self.refresh_page_rows()

    def add_page_row(self, offset: int = 0, skip_slots=None):
        row = PdfPageRuleRow(len(self.page_rows) + 1, self.labels_per_page, offset, skip_slots, self)
        row.remove_button.clicked.connect(lambda: self.remove_page_row(row))
        self.page_rows.append(row)
        self.rows_layout.addWidget(row)
        self.refresh_page_rows()

    def remove_page_row(self, row: PdfPageRuleRow):
        self.page_rows.remove(row)
        row.setParent(None)
        row.deleteLater()
        self.refresh_page_rows()

    def get_configured_rows(self):
        return [row for row in self.page_rows if row.is_configured()]

    def refresh_page_rows(self):
        self.empty_state_label.setVisible(not self.page_rows)
        for index, row in enumerate(self.page_rows, start=1):
            row.set_page_number(index)

    def get_draw_borders(self) -> bool:
        return self.draw_borders_checkbox.isChecked()

    def get_page_options_text(self) -> str:
        return '\n'.join(row.to_line() for row in self.get_configured_rows()).strip()

    def get_page_specs(self):
        return normalize_pdf_page_specs([row.to_line() for row in self.get_configured_rows()])