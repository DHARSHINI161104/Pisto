"""Background camera pipeline: QR identification + calibration + shot detection.

A single thread reads frames from the camera abstraction and drives the app
through its lifecycle:

* MODE_IDLE       -> scans frames for QR codes; a hit selects a known user or
                     sets pending_qr_id so the UI can ask for the newcomer's
                     name.
* MODE_CALIBRATING -> detects the target in the live view, waits until the
                     detection is stable (consecutive frames with a similar
                     centre/scale), then switches to MODE_SHOOTING.
* MODE_SHOOTING  -> keeps the calibrated target warped, feeds frames to the
                    shot detector, and records confirmed holes as scored shots.

The thread never holds the Flask app context; it talks to the DB directly and
mutates AppState (thread-safe).
"""

import threading
import time

import cv2

import config
from app import camera, calibration, state
from app.detection import ShotDetector
from app.qr import QRReader

STOP = threading.Event()

# Sliding window of recent calibrations used for the stability check.
_calibration_window = []


def _jpeg(frame, quality=80):
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes() if ok else None


def _handle_qr(payload):
    st = state.STATE
    user = st.select_user(payload)
    if user is None:
        st.pending_qr_id = payload
        st.log(f"Unknown QR {payload}; waiting for name.")
    else:
        st.pending_qr_id = None
        st.set_mode(state.MODE_CALIBRATING)
        st.log(f"QR accepted: {user['name']}")


def _calibrate(st, frame):
    """Detect the target and, once stable, hand over to live scoring."""
    global _calibration_window
    cal = calibration.detect_target(frame)

    if cal is None:
        _calibration_window.clear()
        st.calibration = None
        st.calibration_state = "searching"
        st.pipeline_error = ("Target not found - aim the camera at the black "
                             "bull and keep it still.")
        st.overlay_jpeg = _jpeg(frame)
        return

    _calibration_window.append(cal)
    if len(_calibration_window) > config.CALIB_MIN_FRAMES:
        _calibration_window.pop(0)

    # Live view shows the detected centre and rings so the operator can verify.
    st.overlay_jpeg = _jpeg(cal.draw_overlay(frame))
    st.calibration = cal
    st.pipeline_error = None

    if len(_calibration_window) < config.CALIB_MIN_FRAMES:
        st.calibration_state = "searching"
        return

    stable = all(
        _calibration_window[0].similar_to(
            c, config.CALIB_CENTER_TOLERANCE_PX, config.CALIB_SCALE_TOLERANCE)
        for c in _calibration_window)
    if not stable:
        st.calibration_state = "searching"
        return

    # Calibration accepted: build a clean baseline and start scoring.
    st.detector = ShotDetector(cal)
    warped = cal.warp(frame)
    st.detector.set_reference(cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY))
    st.calibration_state = "ready"
    st.set_mode(state.MODE_SHOOTING)
    _calibration_window.clear()
    st.log(f"Target calibrated: centre ({cal.cx:.0f},{cal.cy:.0f}) px, "
           f"{cal.scale_px_per_mm:.2f} px/mm. Waiting for shots.")


def _handle_frame(st, frame):
    if st.mode == state.MODE_IDLE:
        st.overlay_jpeg = _jpeg(frame)
        for payload in QRReader().detect(frame):
            _handle_qr(payload)
        return

    if st.mode == state.MODE_CALIBRATING:
        _calibrate(st, frame)
        return

    if st.mode == state.MODE_SHOOTING:
        if st.calibration is None or st.detector is None:
            st.set_mode(state.MODE_CALIBRATING)
            _calibrate(st, frame)
            return
        warped = st.calibration.warp(frame)
        warped_gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
        new_holes = st.detector.update(warped_gray)
        overlay = st.detector.last_overlay
        if overlay is not None:
            st.overlay_jpeg = _jpeg(overlay)
        for mm_x, mm_y in new_holes:
            st.add_detected_shot(mm_x, mm_y)


def _run():
    while not STOP.is_set():
        frame = camera.read_frame()
        if frame is None:
            time.sleep(0.1)
            continue
        try:
            _handle_frame(state.STATE, frame)
        except Exception as exc:  # keep the thread alive on any error
            state.STATE.pipeline_error = f"{type(exc).__name__}: {exc}"
            time.sleep(0.5)


def start():
    camera.start()
    if not camera.available():
        state.STATE.set_mode(state.MODE_MANUAL)
        state.STATE.log("No camera detected - running in manual-entry mode.")
        return
    thread = threading.Thread(target=_run, daemon=True, name="camera-pipeline")
    thread.start()
    state.STATE.log(f"Camera ready ({camera.backend_name()}).")


def stop():
    STOP.set()