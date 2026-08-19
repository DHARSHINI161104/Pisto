"""Target calibration: find the ISSF target in a frame and relate pixels to mm.

The black bull (rings 4-10, 107.5mm diameter) is the calibration reference. It
is detected by thresholding and fitting an ellipse; the ellipse lets us build a
fronto-parallel warped view of the target and a pixels-per-millimetre scale.
"""

import math

import cv2
import numpy as np

from config import (BLACK_AREA_DIAMETER_MM, RING_RADII_MM, INNER_TEN_RADIUS_MM,
                    CALIB_MIN_ASPECT, GAUSSIAN_KERNEL, GAUSSIAN_SIGMA)

BLACK_RADIUS_MM = BLACK_AREA_DIAMETER_MM / 2.0


class Calibration:
    def __init__(self, cx, cy, semi_a, semi_b, angle_deg, scale_px_per_mm,
                 v_major=None, v_minor=None):
        self.cx = float(cx)
        self.cy = float(cy)
        self.semi_a = float(semi_a)     # major semi-axis (px)
        self.semi_b = float(semi_b)     # minor semi-axis (px)
        self.angle_deg = float(angle_deg)
        self.scale_px_per_mm = float(scale_px_per_mm)
        self.aspect = float(semi_b) / float(semi_a) if semi_a else 0.0
        if v_major is None:
            # Back-compat: fall back to the old (cos, sin) major-axis guess.
            th = math.radians(self.angle_deg)
            v_major = (math.cos(th), math.sin(th))
        self._v_major = np.array(v_major, dtype=np.float64)
        if v_minor is None:
            v_minor = (-self._v_major[1], self._v_major[0])
        self._v_minor = np.array(v_minor, dtype=np.float64)
        self._affine = self._build_affine()

    def similar_to(self, other, center_tol_px, scale_tol):
        """True when this calibration matches another within tolerances."""
        if other is None:
            return False
        return (abs(self.cx - other.cx) <= center_tol_px
                and abs(self.cy - other.cy) <= center_tol_px
                and abs(self.scale_px_per_mm - other.scale_px_per_mm)
                <= scale_tol * other.scale_px_per_mm)

    def draw_overlay(self, frame, holes_px=(), color=(0, 255, 0)):
        """Draw the detected centre, black bull and scoring rings on a frame."""
        out = np.array(frame, copy=True)
        cx, cy = int(self.cx), int(self.cy)
        cv2.line(out, (cx - 40, cy), (cx + 40, cy), color, 1)
        cv2.line(out, (cx, cy - 40), (cx, cy + 40), color, 1)
        cv2.circle(out, (cx, cy), max(int(self.semi_a), 1), color, 2)
        for rr in RING_RADII_MM.values():
            cv2.circle(out, (cx, cy), max(int(rr * self.scale_px_per_mm), 1),
                       (0, 255, 255), 1)
        cv2.circle(out, (cx, cy),
                   max(int(INNER_TEN_RADIUS_MM * self.scale_px_per_mm), 1),
                   (0, 0, 255), 2)
        for hx, hy in holes_px:
            cv2.circle(out, (int(hx), int(hy)), 6, (0, 0, 255), 2)
        return out

    def _build_affine(self):
        """Affine 3x3 mapping mm coords (origin at target centre) to image px."""
        s_px = self.scale_px_per_mm
        vm, vn = self._v_major, self._v_minor
        # mm(1,0) lands on the major axis, mm(0,1) on the minor axis.
        return np.array([
            [s_px * vm[0], s_px * vn[0], self.cx],
            [s_px * vm[1], s_px * vn[1], self.cy],
            [0, 0, 1],
        ], dtype=np.float64)

    def project(self, mm_x, mm_y):
        """Map target-plane mm coords to pixel coords (x, y)."""
        v = self._affine @ np.array([mm_x, mm_y, 1.0])
        return float(v[0]), float(v[1])

    def to_pixel_radius_mm(self, radius_mm):
        """Convert a mm radius to pixels on this calibration."""
        return radius_mm * self.scale_px_per_mm

    def warp(self, frame):
        """Return a fronto-parallel view of the target (perfect circles).

        The warped image has the target centre at mid-image and a uniform
        scale of self.scale_px_per_mm px/mm, so ring radii in pixels are
        radius_mm * scale.

        Linear map L sends the detected ellipse's major axis onto the image
        x-axis (unit length) and the minor axis onto the y-axis stretched by
        a/b, turning the projected bull back into a circle of radius a. NOTE:
        the installed OpenCV applies the warpAffine matrix as a *forward*
        src->dst transform (same convention as getAffineTransform), so this M
        maps src coordinates.
        """
        side = max(2 * int(self.semi_a) + 20, 64)
        off = side / 2.0
        a = self.semi_a
        b = max(self.semi_b, 1e-6)
        vm, vn = self._v_major, self._v_minor
        # L = diag(1, a/b) * inv([vm | vn]); axes are orthonormal so inv = T.
        Lin = np.array([
            [vm[0], vm[1]],
            [(a / b) * vn[0], (a / b) * vn[1]],
        ], dtype=np.float64)
        t = [off - Lin[0, 0] * self.cx - Lin[0, 1] * self.cy,
             off - Lin[1, 0] * self.cx - Lin[1, 1] * self.cy]
        M = np.array([[Lin[0, 0], Lin[0, 1], t[0]],
                      [Lin[1, 0], Lin[1, 1], t[1]]], dtype=np.float64)
        return cv2.warpAffine(frame, M, (side, side))


def detect_target(frame):
    """Find the black bull in a frame.

    Returns a Calibration or None when the target cannot be located.
    """
    if frame is None:
        return None
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, GAUSSIAN_KERNEL, GAUSSIAN_SIGMA)
    _, mask = cv2.threshold(gray, 70, 255, cv2.THRESH_BINARY_INV)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    moments = cv2.moments(mask)
    if moments["m00"] < 2000:
        return None
    cx = moments["m10"] / moments["m00"]
    cy = moments["m01"] / moments["m00"]
    mu20 = moments["mu20"] / moments["m00"]
    mu11 = moments["mu11"] / moments["m00"]
    mu02 = moments["mu02"] / moments["m00"]
    cov = np.array([[mu20, mu11], [mu11, mu02]])
    evals, evecs = np.linalg.eigh(cov)
    imax = int(np.argmax(evals))
    semi_a = 2.0 * math.sqrt(max(evals[imax], 0.0))
    semi_b = 2.0 * math.sqrt(max(evals[1 - imax], 0.0))
    if semi_a <= 1:
        return None
    if semi_b / semi_a < CALIB_MIN_ASPECT:
        return None
    v_major = evecs[:, imax]
    v_minor = evecs[:, 1 - imax]
    scale = semi_a / BLACK_RADIUS_MM
    angle_deg = math.degrees(math.atan2(v_major[1], v_major[0]))
    return Calibration(cx, cy, semi_a, semi_b, angle_deg, scale,
                       v_major=v_major, v_minor=v_minor)


def find_target_and_warp(frame):
    """Convenience: calibrate and warp in one call."""
    cal = detect_target(frame)
    if cal is None:
        return None, None
    return cal, cal.warp(frame)