"""End-to-end camera workflow: calibrate -> wait -> shot -> score -> store.

Feeds synthetic camera frames through the real pipeline functions
(pipeline._handle_frame) to verify the whole automatic-scoring flow without a
webcam.
"""

import cv2
import numpy as np
import pytest

import config
from app import db, pipeline, state
from app.calibration import BLACK_RADIUS_MM


def _camera_frame(side=640, holes_mm=(), px_per_mm=3.0):
    """A realistic-looking BGR camera frame with a black bull and optional holes."""
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


@pytest.fixture(autouse=True)
def clean():
    db.init_db()
    conn = db._connect()
    conn.execute("DELETE FROM shots")
    conn.execute("DELETE FROM games")
    conn.execute("DELETE FROM users")
    conn.commit()
    pipeline._calibration_window.clear()
    st = state.STATE
    st.mode = state.MODE_IDLE
    st.calibration = None
    st.detector = None
    st.calibration_state = "none"
    st.active_user = None
    st.active_game_id = None
    st.game = None
    yield


def _run_calibration_and_warmup():
    st = state.STATE
    st.select_user("CAM-001", "Cam Shooter")
    st.set_mode(state.MODE_CALIBRATING)
    clean_frame = _camera_frame()
    for _ in range(config.CALIB_MIN_FRAMES + 2):
        pipeline._handle_frame(st, clean_frame)
    assert st.mode == state.MODE_SHOOTING
    assert st.calibration_state == "ready"
    # Let the detector blend a clean baseline.
    for _ in range(config.DETECTOR_WARMUP_FRAMES + 1):
        pipeline._handle_frame(st, clean_frame)
    assert st.game["shots"] == []


def test_calibration_then_shot_scored_and_stored():
    _run_calibration_and_warmup()
    st = state.STATE

    target = (10.0, 0.0)   # d = 10mm -> 9.4
    shot_frame = _camera_frame(holes_mm=[target])
    for _ in range(config.MIN_HOLE_PERSIST_FRAMES + 2):
        pipeline._handle_frame(st, shot_frame)

    shots = db.shots_for_game(st.active_game_id)
    assert len(shots) == 1
    assert shots[0]["score"] == 9.4
    assert 9.0 < shots[0]["x_mm"] < 11.0
    assert st.game_total() == 9.4

    # The same hole must never be counted twice.
    for _ in range(10):
        pipeline._handle_frame(st, shot_frame)
    assert len(db.shots_for_game(st.active_game_id)) == 1


def test_second_shot_after_first():
    _run_calibration_and_warmup()
    st = state.STATE

    first = (10.0, 0.0)
    for _ in range(config.MIN_HOLE_PERSIST_FRAMES + 2):
        pipeline._handle_frame(st, _camera_frame(holes_mm=[first]))

    # Second shot appears on a later frame set.
    second = (-6.0, -8.0)   # d ~ 10mm -> 9.4
    both = [first, second]
    for _ in range(config.MIN_HOLE_PERSIST_FRAMES + 2):
        pipeline._handle_frame(st, _camera_frame(holes_mm=both))

    shots = db.shots_for_game(st.active_game_id)
    assert len(shots) == 2
    assert shots[0]["shot_no"] == 1
    assert shots[1]["shot_no"] == 2
    assert st.game_total() == pytest.approx(shots[0]["score"] + shots[1]["score"], abs=0.1)


def test_target_not_in_view_stays_calibrating():
    st = state.STATE
    st.select_user("CAM-001", "Cam Shooter")
    st.set_mode(state.MODE_CALIBRATING)
    empty = np.full((400, 400, 3), 240, dtype=np.uint8)
    for _ in range(15):
        pipeline._handle_frame(st, empty)
    assert st.mode == state.MODE_CALIBRATING
    assert st.calibration_state == "searching"
    assert st.pipeline_error  # message tells the operator what to do


def test_public_state_includes_coordinates_and_status():
    _run_calibration_and_warmup()
    st = state.STATE

    shot_frame = _camera_frame(holes_mm=[(10.0, 0.0)])
    for _ in range(config.MIN_HOLE_PERSIST_FRAMES + 2):
        pipeline._handle_frame(st, shot_frame)

    pub = st.public_state()
    assert pub["calibration_complete"] is True
    assert pub["target_detected"] is True
    assert pub["status"] == "READY"
    assert pub["current_shot"] is not None
    cs = pub["current_shot"]
    assert cs["shot_no"] == 1
    assert cs["x_mm"] is not None and abs(cs["x_mm"] - 10.0) < 1.5
    assert cs["y_mm"] is not None and abs(cs["y_mm"]) < 1.5
    assert cs["distance_mm"] is not None and abs(cs["distance_mm"] - 10.0) < 1.5
    assert pub["shots"][-1]["x_mm"] == cs["x_mm"]
    assert pub["shots"][-1]["distance_mm"] == cs["distance_mm"]


def test_shot_detected_on_noisy_frames():
    """Gaussian blur must keep detecting a hole under moderate sensor noise."""
    _run_calibration_and_warmup()
    st = state.STATE
    rng = np.random.default_rng(0)

    target = (12.0, 0.0)
    shot_frame = _camera_frame(holes_mm=[target])
    for _ in range(config.MIN_HOLE_PERSIST_FRAMES + 2):
        noise = rng.integers(-8, 9, shot_frame.shape[:2] + (1,))
        noisy = np.clip(shot_frame.astype(np.int16) + noise, 0, 255)
        pipeline._handle_frame(st, noisy.astype(np.uint8))

    shots = db.shots_for_game(st.active_game_id)
    assert len(shots) == 1
    assert abs(shots[0]["x_mm"] - 12.0) < 2.0