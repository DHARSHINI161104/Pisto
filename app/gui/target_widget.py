"""Large target widget painted with QPainter.

Uses the exact scoring geometry from config.RING_RADII_MM / INNER_TEN_RADIUS_MM
/ MAX_SCORING_RADIUS_MM - the same numbers the scoring engine uses. No second
scoring geometry is defined here.
"""

import config
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

CARD_RADIUS_MM = config.TARGET_OUTER_DIAMETER_MM / 2.0
BULL_RADIUS_MM = config.RING_RADII_MM[4]


class TargetWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.shots = []
        self.setMinimumSize(360, 360)

    def set_shots(self, shots):
        self.shots = list(shots)
        self.update()

    # ------------------------------------------------------------- paint --
    def _scale(self):
        c = min(self.width(), self.height()) / 2.0
        return (c - 14.0) / CARD_RADIUS_MM

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(18, 24, 32))

        cx, cy = self.width() / 2.0, self.height() / 2.0
        s = self._scale()

        def r(mm):
            return mm * s

        def pt(mm_x, mm_y):
            return QPointF(cx + mm_x * s, cy + mm_y * s)

        # card
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(245, 247, 250))
        painter.drawEllipse(pt(0, 0), r(CARD_RADIUS_MM), r(CARD_RADIUS_MM))

        # black bull
        painter.setBrush(QColor(20, 20, 22))
        painter.setPen(QPen(QColor(20, 20, 22), max(1.0, 0.25 * s)))
        painter.drawEllipse(pt(0, 0), r(BULL_RADIUS_MM), r(BULL_RADIUS_MM))

        # scoring ring lines: 10..5 white, 4..1 black on the white card
        for ring in range(5, 11):
            painter.setPen(QPen(QColor(245, 247, 250),
                                max(1.0, 0.25 * s)))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(pt(0, 0), r(config.RING_RADII_MM[ring]),
                                r(config.RING_RADII_MM[ring]))
        for ring in range(1, 5):
            painter.setPen(QPen(QColor(20, 20, 22),
                                max(1.0, 0.35 * s)))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(pt(0, 0), r(config.RING_RADII_MM[ring]),
                                r(config.RING_RADII_MM[ring]))

        # inner ten / X
        painter.setPen(QPen(QColor(245, 247, 250), max(1.0, 0.2 * s)))
        painter.drawEllipse(pt(0, 0), r(config.INNER_TEN_RADIUS_MM),
                            r(config.INNER_TEN_RADIUS_MM))

        self._draw_labels(painter, cx, cy, s)

        # shot markers
        if not self.shots:
            return
        for shot in self.shots[:-1]:
            self._draw_marker(painter, pt(shot.x_mm, shot.y_mm),
                              is_current=False)
        self._draw_marker(painter, pt(self.shots[-1].x_mm, self.shots[-1].y_mm),
                          is_current=True)

    def _draw_labels(self, painter, cx, cy, s):
        painter.setPen(QColor(20, 20, 22))
        font_size = max(8, int(1.8 * s))
        for ring in range(1, 11):
            radius_mm = (config.RING_RADII_MM[ring] + config.RING_RADII_MM.get(ring + 1, 0.0)) / 2.0
            rr = radius_mm * s
            painter.setFont(QFont("Arial", max(7, int(0.9 * font_size))))
            for sign in (-1.0, 1.0):
                px, py = cx + sign * rr, cy
                painter.drawText(int(px), int(py), str(ring))

    def _draw_marker(self, painter, p, is_current):
        if is_current:
            painter.setPen(QPen(QColor(220, 40, 40), 2.0))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(p, 9.0, 9.0)
            painter.drawLine(p + QPointF(-13, 0), p + QPointF(13, 0))
            painter.drawLine(p + QPointF(0, -13), p + QPointF(0, 13))
        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(40, 200, 90))
            painter.drawEllipse(p, 5.0, 5.0)