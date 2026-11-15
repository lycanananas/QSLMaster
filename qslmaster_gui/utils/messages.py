"""Message boxes with an explicit text format.

Qt guesses whether a string is HTML (Qt.TextFormat.AutoText). Messages often contain
data from outside (server errors, file paths, configuration names), so they are shown
as plain text unless the caller passes rich=True for its own trusted HTML.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox, QWidget

_Button = QMessageBox.StandardButton


def _exec_box(parent: QWidget, icon: QMessageBox.Icon, title: str, text: str, buttons, rich: bool = False):
    box = QMessageBox(icon, title, text, buttons, parent)
    box.setTextFormat(Qt.TextFormat.RichText if rich else Qt.TextFormat.PlainText)
    return box.exec()


def show_info(parent: QWidget, title: str, text: str, rich: bool = False) -> None:
    _exec_box(parent, QMessageBox.Icon.Information, title, text, _Button.Ok, rich)


def show_warning(parent: QWidget, title: str, text: str, rich: bool = False) -> None:
    _exec_box(parent, QMessageBox.Icon.Warning, title, text, _Button.Ok, rich)


def show_error(parent: QWidget, title: str, text: str, rich: bool = False) -> None:
    _exec_box(parent, QMessageBox.Icon.Critical, title, text, _Button.Ok, rich)


def ask_yes_no(parent: QWidget, title: str, text: str) -> bool:
    return _exec_box(parent, QMessageBox.Icon.Question, title, text, _Button.Yes | _Button.No) == _Button.Yes
