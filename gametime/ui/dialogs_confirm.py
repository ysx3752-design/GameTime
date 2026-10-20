"""通用确认与提示对话框。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..windows import apply_dark_title_bar
from .dialogs import ConfirmDialog
from .theme import COLORS, is_dark_active
from .widgets import Separator


class MessageDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        message: str,
        *,
        danger: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ContentDialog")
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedWidth(430)
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 20)
        root.setSpacing(14)
        title_label = QLabel(title)
        title_label.setProperty("role", "h2")
        title_label.setStyleSheet(f"color: {COLORS['red'] if danger else COLORS['text']};")
        root.addWidget(title_label)
        body = QLabel(message)
        body.setProperty("role", "body")
        body.setWordWrap(True)
        body.setMinimumHeight(48)
        root.addWidget(body)
        root.addWidget(Separator())
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        okay = QPushButton("知道了")
        okay.setProperty("variant", "primary")
        okay.setCursor(Qt.CursorShape.PointingHandCursor)
        okay.setMinimumHeight(35)
        okay.clicked.connect(self.accept)
        buttons.addWidget(okay)
        root.addLayout(buttons)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        apply_dark_title_bar(int(self.winId()), dark=is_dark_active())


def ask_confirm(
    parent: QWidget | None,
    title: str,
    message: str,
    confirm_text: str = "确定",
    *,
    danger: bool = False,
    cancel_text: str = "取消",
) -> bool:
    dialog = ConfirmDialog(
        parent,
        title,
        message,
        confirm_text,
        danger=danger,
        cancel_text=cancel_text,
    )
    return dialog.exec() == QDialog.DialogCode.Accepted


def show_message(
    parent: QWidget | None, title: str, message: str, *, danger: bool = False
) -> None:
    MessageDialog(parent, title, message, danger=danger).exec()
