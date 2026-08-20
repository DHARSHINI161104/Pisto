"""Scoreboard widget: player, session, current shot, total, shot history."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)


class ScoreboardWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(330)

        self.player_label = QLabel("PLAYER 01")
        self.session_label = QLabel("DEMO MATCH")

        self.current_shot = QLabel("--")
        self.shot_x = QLabel("X:   --")
        self.shot_y = QLabel("Y:   --")
        self.shot_dist = QLabel("DIST: --")

        self.total_score = QLabel("0.0")

        self.history = QTableWidget(0, 5)
        self.history.setHorizontalHeaderLabels(
            ["SHOT", "X (mm)", "Y (mm)", "DIST (mm)", "SCORE"])
        self.history.verticalHeader().setVisible(False)
        self.history.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history.setSelectionMode(QTableWidget.NoSelection)
        self.history.horizontalHeader().setStretchLastSection(True)
        self.history.setMinimumHeight(150)

        self._build()
        self.apply_theme()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(8)

        def big(label, size):
            label.setAlignment(Qt.AlignCenter)
            label.setFont(QFont("Arial", size, QFont.Bold))
            return label

        for lbl in (self.player_label, self.session_label):
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFont(QFont("Arial", 15, QFont.Bold))
            root.addWidget(lbl)

        root.addWidget(self._rule())

        root.addWidget(QLabel("CURRENT SHOT"))
        root.addWidget(big(self.current_shot, 46))
        coords = QHBoxLayout()
        for lbl in (self.shot_x, self.shot_y, self.shot_dist):
            lbl.setFont(QFont("Arial", 11))
            lbl.setAlignment(Qt.AlignCenter)
            coords.addWidget(lbl)
        root.addLayout(coords)

        root.addWidget(self._rule())

        root.addWidget(QLabel("TOTAL SCORE"))
        root.addWidget(big(self.total_score, 52))

        root.addWidget(self._rule())

        root.addWidget(QLabel("SHOT HISTORY"))
        root.addWidget(self.history, 1)

    def _rule(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#3a4650;")
        return line

    def apply_theme(self):
        self.setStyleSheet("""
            QWidget { background: #10151b; color: #e8eef2; }
            QLabel { color: #e8eef2; }
            QLabel[big=true] { color: #ffffff; }
            QTableWidget {
                background: #0b0f14; color: #dfe6ea;
                gridline-color: #22303a; border: 1px solid #22303a;
            }
            QHeaderView::section {
                background: #18232c; color: #9fb2bf;
                border: none; padding: 4px;
            }
        """)

    def refresh(self, session):
        self.player_label.setText(session.player)
        self.session_label.setText(session.session_label)

        shot = session.current_shot()
        if shot is None:
            self.current_shot.setText("--")
            self.shot_x.setText("X:   --")
            self.shot_y.setText("Y:   --")
            self.shot_dist.setText("DIST: --")
            self.total_score.setText("0.0")
        else:
            self.current_shot.setText(f"{shot.score:.1f}")
            self.shot_x.setText(f"X:  {shot.x_mm:+.1f} mm")
            self.shot_y.setText(f"Y:  {shot.y_mm:+.1f} mm")
            self.shot_dist.setText(f"DIST: {shot.distance_mm:.1f} mm")
            self.total_score.setText(f"{session.total():.1f}")

        self.history.setRowCount(len(session.shots))
        for row, shot in enumerate(session.shots):
            values = [str(shot.shot_no), f"{shot.x_mm:+.1f}",
                      f"{shot.y_mm:+.1f}", f"{shot.distance_mm:.1f}",
                      f"{shot.score:.1f}"]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                self.history.setItem(row, col, item)
        self.history.resizeColumnsToContents()