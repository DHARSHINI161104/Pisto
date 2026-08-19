import cv2
import numpy as np
import pytest

from app.calibration import detect_target, Calibration, BLACK_RADIUS_MM


def _make_frame(side=600, radius=180, angle=0, offset=0):
    """A simple BGR frame with a black bull (grey card background)."""
    frame = np.full((side, side, 3), 220, dtype=np.uint8)
    c = side // 2 + offset
    cv2.circle(frame, (c, c), radius, (20, 20, 20), -1)
    return frame


def test_detect_target_centered():
    frame = _make_frame()
    cal = detect_target(frame)
    assert cal is not None
    assert abs(cal.cx - 300) < 5 and abs(cal.cy - 300) < 5
    assert cal.scale_px_per_mm == pytest.approx(180 / BLACK_RADIUS_MM, rel=0.1)
    assert cal.aspect > 0.9


def test_detect_target_no_target():
    frame = np.full((400, 400, 3), 240, dtype=np.uint8)
    assert detect_target(frame) is None


def test_similar_to():
    a = Calibration(100, 100, 50, 50, 0, 2.0)
    b = Calibration(105, 98, 50, 50, 0, 2.05)
    assert a.similar_to(b, 15, 0.08)
    far = Calibration(300, 300, 50, 50, 0, 2.0)
    assert not a.similar_to(far, 15, 0.08)


def test_draw_overlay_runs():
    frame = _make_frame()
    cal = detect_target(frame)
    out = cal.draw_overlay(frame, holes_px=[(300, 300)])
    assert out.shape == frame.shape
    assert out.dtype == frame.dtype