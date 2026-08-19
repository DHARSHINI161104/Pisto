"""GUI tests: session scoring (via the existing engine), target rendering,
demo controls and the live camera processor (synthetic frames, no webcam).
"""

import random

import cv2
import numpy as np
import pytest

import config
from app.calibration import BLACK_RADIUS_MM
from app.gui.live import LiveProcessor
from app.gui.session import GuiSession, demo_coordinate
from app.gui.target_widget import TargetWidget
from app.scoring import score_for_offset


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _camera_frame(side=640, holes_mm=(), px_per_mm=3.0):
    frame = np.full((side, side, 3), 220, dtype=np.uint8)
    c = side // 2
    bull_r = int(BLACK_RADIUS_MM * px_per_mm)
    cv2.circle(frame, (c, c), bull_r, (20, 20, 20), -1)
    for mx, my in holes_mm:
        cx = int(c + mx * px_per_mm)
        cy = int(c + my * px_per_mm)
        r = max(int(2.25 * px_per_mm), 4)
        cv2.circle(frame, (cx, cy), r, (120, 120, 120), -1)
    return frame


# ------------------------------------------------------------- session --
def test_session_scores_with_existing_engine():
    s = GuiSession()
    shot = s.add_shot(10.0, 0.0)
    assert shot.score == pytest.approx(score_for_offset(10.0, 0.0), abs=0.1)
    assert shot.score == 9.4
    assert shot.shot_no == 1
    assert shot.distance_mm == pytest.approx(10.0)
    assert shot.x_mm == 10.0
    assert s.total() == pytest.approx(9.4)
    assert s.current_shot() is shot
    assert s.x_count() == 0


def test_session_inner_ten_marked():
    s = GuiSession()
    shot = s.add_shot(1.0, 1.0)      # d = 1.4mm inside the 2.5mm X ring
    assert shot.is_x is True
    assert s.x_count() == 1


def test_session_clear_and_reset():
    s = GuiSession()
    for _ in range(3):
        s.add_demo_shot()
    assert len(s.shots) == 3
    s.clear_shots()
    assert s.shots == []
    s.add_demo_shot()
    s.reset_match()
    assert s.shots == []
    assert s.total() == 0.0


def test_demo_coordinate_inside_scoring_area():
    rng = random.Random(42)
    for _ in range(200):
        x, y = demo_coordinate(rng)
        assert (x ** 2 + y ** 2) ** 0.5 <= 70.0
        assert score_for_offset(x, y) >= 0.0


def test_session_demo_live_transitions():
    s = GuiSession()
    assert s.mode == "demo" and s.camera_state == "standby"
    s.set_live()
    assert s.mode == "live" and s.system_state == "ACTIVE"
    s.set_camera_state("connected")
    assert s.camera_state == "connected"
    s.set_demo()
    assert s.mode == "demo" and s.camera_state == "standby"


# -------------------------------------------------------------- widget --
def test_target_widget_renders_bull_and_card(qapp):
    from PySide6.QtGui import QImage
    w = TargetWidget()
    w.resize(400, 400)
    w.set_shots([])
    img = w.grab().toImage()
    img = img.convertToFormat(QImage.Format.Format_RGB888)
    assert not img.isNull()
    center = img.pixelColor(200, 200)
    assert center.red() < 60        # dark black bull at centre
    edge = img.pixelColor(330, 200)
    assert edge.red() > 220         # white card between bull and card edge
    # painted region non-empty (card circle spans most of the widget)
    assert img.pixelColor(2, 2).red() < 60  # dark background outside card


def test_target_widget_draws_markers(qapp):
    from PySide6.QtGui import QImage
    from app.gui.session import Shot
    w = TargetWidget()
    w.resize(400, 400)
    prev = Shot(1, 30.0, 0.0, 30.0, 8.5)
    cur = Shot(2, 0.0, 20.0, 20.0, 9.0)
    w.set_shots([prev, cur])
    img = w.grab().toImage().convertToFormat(QImage.Format.Format_RGB888)
    assert not img.isNull()


# --------------------------------------------------------------- live ---
def _calibrate(proc):
    clean = _camera_frame()
    for _ in range(config.CALIB_MIN_FRAMES + 2):
        shots, _ = proc.step(clean)
        assert shots == []
    assert proc.status == "ready"
    for _ in range(config.DETECTOR_WARMUP_FRAMES + 1):
        proc.step(clean)


def test_live_processor_calibrates_and_scores_shot():
    proc = LiveProcessor()
    _calibrate(proc)

    target = (10.0, 0.0)
    shot_frame = _camera_frame(holes_mm=[target])
    found = []
    for _ in range(config.MIN_HOLE_PERSIST_FRAMES + 2):
        shots, overlay = proc.step(shot_frame)
        found.extend(shots)
        assert overlay is not None

    assert len(found) == 1
    assert abs(found[0][0] - 10.0) < 1.5
    # the score for that coordinate uses the same engine as everything else
    assert score_for_offset(found[0][0], found[0][1]) == pytest.approx(9.4, abs=0.2)


def test_live_processor_never_rescores_same_hole():
    proc = LiveProcessor()
    _calibrate(proc)

    shot_frame = _camera_frame(holes_mm=[(10.0, 0.0)])
    found = []
    for _ in range(config.MIN_HOLE_PERSIST_FRAMES + 2):
        shots, _ = proc.step(shot_frame)
        found.extend(shots)
    for _ in range(10):
        shots, _ = proc.step(shot_frame)
        found.extend(shots)
    assert len(found) == 1


def test_live_processor_stays_searching_without_target():
    proc = LiveProcessor()
    empty = np.full((400, 400, 3), 240, dtype=np.uint8)
    for _ in range(15):
        shots, _ = proc.step(empty)
        assert shots == []
    assert proc.status == "searching"
    assert proc.calibration is None


def test_live_processor_status_sequence():
    proc = LiveProcessor()
    assert proc.status == "standby"
    shots, _ = proc.step(_camera_frame())
    assert proc.status == "searching"
    _calibrate(proc)
    assert proc.status == "ready"