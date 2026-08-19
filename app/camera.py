"""Camera abstraction.

Works on Raspberry Pi 5 (Camera Module via picamera2, or a USB webcam via
OpenCV) and on Windows (USB webcam via OpenCV). When no camera is available the
app keeps running in manual-entry mode only.
"""

import os
import time
import threading

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
    """Open the camera if possible. Safe to call more than once."""
    global _impl, _available
    if _impl is not None:
        return _available
    if os.environ.get("RIFLE_DISABLE_CAMERA"):
        _available = False
        return _available
    _impl = _open_camera()
    _available = _impl is not None and _impl._ok
    return _available


def available():
    return _available


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
