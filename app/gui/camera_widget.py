"""Optional live camera feed view shown inside the same GUI window."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class CameraWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._label = QLabel("CAMERA STANDBY")
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setMinimumSize(320, 200)
        self._label.setStyleSheet(
            "QLabel { background:#0b0f14; color:#9fb2bf; border:1px solid #22303a; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self._label)

    def set_frame(self, qimage):
        pix = QPixmap.fromImage(qimage)
        self._label.setPixmap(pix.scaled(
            self._label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def set_standby(self):
        self._label.setPixmap(QPixmap())
        self._label.setText("CAMERA STANDBY")