"""Camera abstraction.

Works on Raspberry Pi 5 (Camera Module via picamera2, or a USB webcam via
OpenCV) and on Windows (USB webcam via OpenCV). When no camera is available the
app keeps running in manual-entry mode only.
"""

import math
import os
import random
import time
import threading

import cv2

import config

_frame_lock = threading.Lock()
_last_frame = None
_available = False
_impl = None


class _OpenCVBackend:
    name = "opencv"

    def __init__(self, source=config.CAMERA_SOURCE):
        import cv2
        self.cap = cv2.VideoCapture(source)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, config.CAMERA_FPS)
        self._ok = self.cap.isOpened()

    def read(self):
        ok, frame = self.cap.read()
        if not ok:
            time.sleep(0.05)
            return None
        return frame

    def release(self):
        if getattr(self, "cap", None):
            self.cap.release()


class _Picamera2Backend:
    name = "picamera2"

    def __init__(self):
        from picamera2 import Picamera2
        self.picam = Picamera2()
        cfg = self.picam.create_still_configuration(
            main={"size": (config.CAMERA_WIDTH, config.CAMERA_HEIGHT)})
        self.picam.configure(cfg)
        self.picam.start()
        self._ok = True

    def read(self):
        import numpy as np
        frame = self.picam.capture_array()
        if frame is None:
            time.sleep(0.05)
            return None
        # picamera2 delivers RGB(A); OpenCV pipeline expects BGR.
        return np.ascontiguousarray(frame[:, :, ::-1])

    def release(self):
        if getattr(self, "picam", None):
            self.picam.stop()


def _demo_hole():
    """Random shot position (mm) inside the scoring area for the demo camera."""
    radius = config.MAX_SCORING_RADIUS_MM * 0.9 * math.sqrt(random.random())
    angle = random.uniform(0.0, 2.0 * math.pi)
    return radius * math.cos(angle), radius * math.sin(angle)


class _DemoBackend:
    """Synthetic camera: renders the ISSF target so the display panel can run
    and show the live OpenCV view without a real webcam.

    A new pellet hole is punched every DEMO_SHOT_INTERVAL seconds; the normal
    pipeline then detects it exactly like a real shot (one hole = one score).
    """

    name = "demo"

    def __init__(self):
        self._holes = []
        self._last_hole_at = 0.0
        self._frame = None

    def read(self):
        from app.detection import generate_synthetic_target
        now = time.time()
        if now - self._last_hole_at >= config.DEMO_SHOT_INTERVAL:
            self._holes.append(_demo_hole())
            self._last_hole_at = now
            self._frame = None
        if self._frame is None:
            gray, _ = generate_synthetic_target(
                side=config.CAMERA_HEIGHT, holes_mm=self._holes)
            self._frame = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        return self._frame

    def release(self):
        pass


def _open_camera():
    """Try picamera2 first (Pi 5), then a generic OpenCV capture."""
    try:
        return _Picamera2Backend()
    except Exception:
        pass
    try:
        return _OpenCVBackend()
    except Exception:
        return None


def start():
    """Open the camera if possible. Safe to call more than once.

    When RIFLE_DEMO_CAMERA=1 and no real camera is present, a synthetic demo
    target is used so the display can still show the live OpenCV view.
    """
    global _impl, _available
    if _impl is not None:
        return _available
    if os.environ.get("RIFLE_DISABLE_CAMERA"):
        _available = False
        return _available
    _impl = _open_camera()
    _available = _impl is not None and _impl._ok
    if _available:
        # A capture can be "opened" yet deliver no frames (e.g. a dead
        # device); treat that the same as having no camera.
        probe = _impl.read()
        if probe is None:
            try:
                _impl.release()
            except Exception:
                pass
            _impl = None
            _available = False
    if not _available and os.environ.get("RIFLE_DEMO_CAMERA"):
        _impl = _DemoBackend()
        _available = True
    return _available


def available():
    return _available


def release():
    """Release the camera if open. Safe to call any time."""
    global _impl, _available, _last_frame
    if _impl is not None:
        try:
            _impl.release()
        except Exception:
            pass
        _impl = None
        _available = False
        _last_frame = None


def read_frame():
    """Return the latest camera frame as a BGR numpy array (or None)."""
    if _impl is None or not _available:
        return None
    frame = _impl.read()
    if frame is None:
        return None
    with _frame_lock:
        global _last_frame
        _last_frame = frame
    return frame


def last_frame():
    with _frame_lock:
        return _last_frame


def backend_name():
    return _impl.name if _impl else "none"
