"""Live camera processing for the GUI.

Reuses the existing camera abstraction (app.camera), target calibration
(app.calibration) and shot detector (app.detection.ShotDetector) - the same
modules the web pipeline uses. LiveProcessor.step() is a pure function so the
camera path can be unit-tested with synthetic frames; LiveWorker wraps it in a
QThread and forwards results to the GUI via Qt signals.
"""

import threading
import time

import cv2
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

import config
from app import camera, calibration
from app.detection import ShotDetector


def bgr_to_qimage(frame):
    """Convert a BGR numpy frame to a QImage (kept alive via .copy())."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, _ = rgb.shape
    return QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()


class LiveProcessor:
    """Calibrate on the fly, then detect shots. Mirrors app/pipeline logic."""

    def __init__(self):
        self.calibration = None
        self.detector = None
        self._window = []
        self.status = "standby"    # standby|connected|searching|ready

    def reset(self):
        self.calibration = None
        self.detector = None
        self._window = []
        self.status = "standby"

    def step(self, frame):
        """Process one camera frame.

        Returns (shots, overlay_bgr) where shots is a list of (mm_x, mm_y)
        newly detected on this frame and overlay_bgr is the annotated view.
        """
        shots = []
        if self.calibration is None:
            cal = calibration.detect_target(frame)
            if cal is None:
                self._window.clear()
                self.status = "searching"
                return [], frame
            self._window.append(cal)
            if len(self._window) > config.CALIB_MIN_FRAMES:
                self._window.pop(0)
            overlay = cal.draw_overlay(frame)
            if len(self._window) < config.CALIB_MIN_FRAMES or not all(
                    self._window[0].similar_to(
                        c, config.CALIB_CENTER_TOLERANCE_PX,
                        config.CALIB_SCALE_TOLERANCE)
                    for c in self._window):
                self.status = "searching"
                return [], overlay
            self.calibration = cal
            self.detector = ShotDetector(cal)
            self.detector.set_reference(
                cv2.cvtColor(cal.warp(frame), cv2.COLOR_BGR2GRAY))
            self.status = "ready"
            return [], overlay

        warped = self.calibration.warp(frame)
        warped_gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
        new_holes = self.detector.update(warped_gray)
        overlay = (self.detector.last_overlay
                   if self.detector.last_overlay is not None
                   else self.calibration.draw_overlay(frame))
        for mm_x, mm_y in new_holes:
            shots.append((mm_x, mm_y))
        return shots, overlay


class LiveWorker(QThread):
    shot_detected = Signal(float, float)
    frame_ready = Signal(object)      # QImage of the annotated camera view
    status_changed = Signal(str)      # standby|connected|searching|ready

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop = threading.Event()
        self.processor = LiveProcessor()

    def stop(self):
        self._stop.set()

    def run(self):
        camera.start()
        if not camera.available():
            self.status_changed.emit("standby")
            return
        self.status_changed.emit("connected")
        while not self._stop.is_set():
            frame = camera.read_frame()
            if frame is None:
                time.sleep(0.05)
                continue
            try:
                shots, overlay = self.processor.step(frame)
            except Exception:
                continue
            self.status_changed.emit(self.processor.status)
            if overlay is not None:
                self.frame_ready.emit(bgr_to_qimage(overlay))
            for mm_x, mm_y in shots:
                self.shot_detected.emit(mm_x, mm_y)
        camera.release()