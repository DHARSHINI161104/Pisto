"""GUI session state: one model used by both demo and live camera modes.

The scoring is never re-implemented here - shot scores come from
app.scoring.score_for_offset (which uses the same RING_RADII_MM geometry as the
whole project). This class is a plain QObject so it can be unit-tested without
a window and driven by either the demo buttons or the live camera worker.
"""

import math
import random
import re
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

import config
from app.scoring import score_for_offset, is_inner_ten


@dataclass
class Shot:
    shot_no: int
    x_mm: float
    y_mm: float
    distance_mm: float
    score: float
    is_x: bool = False


def demo_coordinate(rng=None):
    """Random sample coordinate (mm) inside the scoring area, from target centre."""
    rng = rng or random
    radius = 70.0 * math.sqrt(rng.random())
    angle = rng.uniform(0.0, 2.0 * math.pi)
    return radius * math.cos(angle), radius * math.sin(angle)


class GuiSession(QObject):
    shots_changed = Signal()
    status_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.shots = []                    # list[Shot]
        self.mode = "demo"                 # 'demo' | 'live'
        self.camera_state = "ready"        # neutral (ready) | connected | active
        self.system_state = "READY"        # 'READY' | 'ACTIVE' | 'COMPLETE'
        self.player = "PLAYER 01"
        self.session_label = "DEMO MATCH"
        self.round_complete = False        # True after the 10th shot

    # ------------------------------------------------------------- model --
    def add_shot(self, x_mm, y_mm, mode=None):
        """Score and append ONE new shot.

        Returns the scored Shot, or None when the shot is a re-detection of the
        last shot or the player's round is over (10-shot limit). A single
        physical shot therefore never creates more than one history entry.
        """
        if self.round_complete or len(self.shots) >= config.SHOTS_PER_GAME:
            return None   # round over - do not accept shot 11+
        if self.shots:
            # Same hole re-appearing in later frames must not be re-scored.
            last = self.shots[-1]
            if math.hypot(x_mm - last.x_mm, y_mm - last.y_mm) \
                    < config.HOLE_MIN_SEPARATION_MM:
                return None
        distance = math.hypot(x_mm, y_mm)
        score = round(score_for_offset(x_mm, y_mm), 1)
        shot = Shot(shot_no=len(self.shots) + 1,
                    x_mm=round(x_mm, 1), y_mm=round(y_mm, 1),
                    distance_mm=round(distance, 1), score=score,
                    is_x=is_inner_ten(distance))
        self.shots.append(shot)
        if len(self.shots) >= config.SHOTS_PER_GAME:
            self.round_complete = True
            self.system_state = "COMPLETE"
        self.shots_changed.emit()
        self.status_changed.emit()
        return shot

    def add_demo_shot(self):
        x, y = demo_coordinate()
        return self.add_shot(x, y, mode="demo")

    def clear_shots(self):
        self.shots = []
        self.round_complete = False
        self.system_state = "READY"
        self.shots_changed.emit()
        self.status_changed.emit()

    def reset_match(self):
        self.player = "PLAYER 01"
        self.shots = []
        self.round_complete = False
        self.system_state = "READY"
        self.session_label = "DEMO MATCH" if self.mode == "demo" else "LIVE MATCH"
        self.shots_changed.emit()
        self.status_changed.emit()

    def next_player(self):
        """Start the next player's fresh round (NEXT button).

        Clears all shots/markers/history, resets the score to 0.0 and the shot
        counter to 0, and moves to the next player number. Nothing is scored
        until the NEXT button is pressed.
        """
        try:
            num = int(re.search(r"(\d+)", self.player).group(1)) + 1
        except (AttributeError, ValueError):
            num = 2
        self.player = f"PLAYER {num:02d}"
        self.shots = []
        self.round_complete = False
        self.system_state = "READY"
        self.session_label = "DEMO MATCH" if self.mode == "demo" else "LIVE MATCH"
        self.shots_changed.emit()
        self.status_changed.emit()

    # ------------------------------------------------------------- state --
    def total(self):
        return round(sum(s.score for s in self.shots), 1)

    def x_count(self):
        return sum(1 for s in self.shots if s.is_x)

    def current_shot(self):
        return self.shots[-1] if self.shots else None

    def set_live(self):
        self.mode = "live"
        self.system_state = "ACTIVE"
        self.session_label = "LIVE MATCH"
        self.status_changed.emit()

    def set_demo(self):
        self.mode = "demo"
        self.system_state = "READY"
        self.camera_state = "ready"     # neutral: not connected, still ready
        self.session_label = "DEMO MATCH"
        self.status_changed.emit()

    def set_camera_state(self, state):
        self.camera_state = state
        self.status_changed.emit()