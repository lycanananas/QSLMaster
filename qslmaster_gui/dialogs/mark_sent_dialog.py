from datetime import date

from PyQt6.QtWidgets import (
    QDateEdit, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QListWidget, QVBoxLayout
)
from PyQt6.QtCore import QDate, Qt

from qslmaster_cli.mark_sent import MarkSentPlan
from qslmaster_cli.qso_utils import format_qso_log_label

SENT_VIA_LABELS = {
    'B': 'bureau',
    'D': 'direct',
    'E': 'electronic',
    'M': 'manager',
}


def describe_match_fields(fields: dict) -> str:
    parts = [SENT_VIA_LABELS.get(fields.get('qsl_sent_via', ''), 'sent')]
    if fields.get('qsl_via'):
        parts.append(f"via {fields['qsl_via']}")
    return ', '.join(parts)


class MarkSentDialog(QDialog):
    def __init__(self, plan: MarkSentPlan, adif_path: str, parent=None):
        super().__init__(parent)
        self.plan = plan
        self.setWindowTitle("Mark as Sent in Wavelog")
        self.setMinimumWidth(560)
        layout = QVBoxLayout()

        file_label = QLabel(f"ADIF file: {adif_path}")
        file_label.setTextFormat(Qt.TextFormat.PlainText)
        file_label.setWordWrap(True)
        layout.addWidget(file_label)

        summary_label = QLabel(
            f"Matched in Wavelog: {len(plan.matched)}\n"
            f"Not found in Wavelog: {len(plan.not_found)}\n"
            f"Ambiguous (skipped): {len(plan.ambiguous)}"
        )
        layout.addWidget(summary_label)

        layout.addWidget(QLabel("QSOs that will be marked as sent:"))
        matched_list = QListWidget()
        for match in plan.matched:
            matched_list.addItem(f"{format_qso_log_label(match.qso)} {match.qso.get('BAND', '')} - {describe_match_fields(match.fields)}")
        matched_list.setMinimumHeight(220)
        layout.addWidget(matched_list)

        if plan.not_found or plan.ambiguous:
            skipped_note = QLabel("QSOs that were not found, or that matched more than one Wavelog QSO, are listed in the processing log and stay unchanged.")
            skipped_note.setWordWrap(True)
            layout.addWidget(skipped_note)

        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("QSL Sent Date:"))
        self.sent_date_input = QDateEdit()
        self.sent_date_input.setCalendarPopup(True)
        self.sent_date_input.setDate(QDate.currentDate())
        date_layout.addWidget(self.sent_date_input)
        date_layout.addStretch()
        layout.addLayout(date_layout)

        fields_note = QLabel("Wavelog fields set for each QSO: QSL sent = Yes, sent via, QSL via and QSL sent date. Requires Wavelog 3.2.5 or later.")
        fields_note.setWordWrap(True)
        layout.addWidget(fields_note)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(f"Mark {len(plan.matched)} QSO(s) as Sent")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def get_sent_date(self) -> date:
        return self.sent_date_input.date().toPyDate()
