"""Live shot-hole detection.

Works on the *warped* (fronto-parallel) target image where the target is a
perfect circle with a known pixels-per-mm scale. A running reference frame
(clean target) is kept; any persistent change of plausible pellet size is
reported as a new hole. Holes are stored in millimetres from target centre.
"""

import cv2
import numpy as np

import config


class ShotDetector:
    def __init__(self, calibration):
        self.cal = calibration
        self._reference = None
        self._candidates = {}          # tracked_key -> [seen_count, mm_x, mm_y]
        self.holes = []                # list of (mm_x, mm_y)
        self.last_frame = None
        self.last_overlay = None
        self.warmup = config.DETECTOR_WARMUP_FRAMES
        self.cooldown = 0              # frames left before detection resumes

    # ------------------------------------------------------------- setup --
    def _blur(self, warped_gray):
        """Gaussian-blur a warped grey frame (noise reduction before diff)."""
        return cv2.GaussianBlur(np.asarray(warped_gray, dtype=np.uint8),
                                config.GAUSSIAN_KERNEL, config.GAUSSIAN_SIGMA)

    def set_reference(self, warped_gray):
        self._reference = np.asarray(self._blur(warped_gray), dtype=np.float32)
        self._candidates.clear()
        self.warmup = config.DETECTOR_WARMUP_FRAMES
        self.cooldown = 0

    def reset_holes(self):
        self.holes = []
        self._candidates.clear()
        self.cooldown = 0

    # --------------------------------------------------------- geometry ---
    def _area_range_px(self):
        s = self.cal.scale_px_per_mm
        lo = np.pi * (config.MIN_HOLE_RADIUS_MM * s) ** 2
        hi = np.pi * (config.MAX_HOLE_RADIUS_MM * s) ** 2
        return lo, hi

    def _to_mm(self, cx_px, cy_px, side):
        """Warped-view px (origin at image centre) -> mm offset from centre."""
        mm_x = (cx_px - side / 2.0) / self.cal.scale_px_per_mm
        mm_y = (cy_px - side / 2.0) / self.cal.scale_px_per_mm
        return mm_x, mm_y

    # ---------------------------------------------------------- detection --
    def update(self, warped_gray):
        """Feed a warped grey frame; return newly confirmed holes in mm.

        A shot is only scored when a diff blob of plausible pellet size appears
        at a STABLE position on MIN_HOLE_PERSIST_FRAMES CONSECUTIVE frames.
        Candidates whose centroid jumps more than SHOT_TRACK_RADIUS_MM are
        treated as noise and reset. After a confirmed shot the reference is
        healed (the hole stops diffing) and SHOT_COOLDOWN_FRAMES of quiet time
        is enforced - so one change is scored once, not repeatedly.
        """
        if self._reference is None:
            self.set_reference(warped_gray)
            return []
        frame = np.asarray(self._blur(warped_gray), dtype=np.float32)
        if self.warmup > 0:
            # Blend the baseline towards the current frame while the image
            # settles after calibration; no shots are scored yet.
            self._reference = self._reference * 0.6 + frame * 0.4
            self.warmup -= 1
            self.last_frame = warped_gray
            self.last_overlay = self.draw_overlay(warped_gray, self.holes)
            return []
        if self.cooldown > 0:
            # Quiet time after a shot: let the scene settle back into baseline.
            self.cooldown -= 1
            self._reference = self._reference * 0.9 + frame * 0.1
            self._candidates.clear()
            self.last_frame = warped_gray
            self.last_overlay = self.draw_overlay(warped_gray, self.holes)
            return []

        diff = cv2.absdiff(frame, self._reference)
        side = frame.shape[0]
        lo_area, hi_area = self._area_range_px()

        _, thresh = cv2.threshold(diff, config.DIFF_THRESHOLD, 255, cv2.THRESH_BINARY)
        thresh = np.uint8(thresh)  # findContours requires CV_8UC1
        thresh = cv2.morphologyEx(
            thresh, cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)

        changed = False
        matched = set()   # candidate keys still alive this frame
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < lo_area * 0.5 or area > hi_area * 3.0:
                continue
            M = cv2.moments(cnt)
            if M["m00"] == 0:
                continue
            cx = M["m10"] / M["m00"]
            cy = M["m01"] / M["m00"]
            mm_x, mm_y = self._to_mm(cx, cy, side)
            # Distance to centre must stay on/near the target (allow ring 1+).
            if (mm_x ** 2 + mm_y ** 2) ** 0.5 > config.RING_RADII_MM[1] + 8:
                continue
            if self._is_known(mm_x, mm_y):
                continue
            changed = True
            best_key, best_d = None, config.SHOT_TRACK_RADIUS_MM
            for key, (count, kx, ky) in self._candidates.items():
                d = ((mm_x - kx) ** 2 + (mm_y - ky) ** 2) ** 0.5
                if d < best_d:
                    best_key, best_d = key, d
            if best_key is None:
                # New candidate at this frame's position.
                key = (round(mm_x, 1), round(mm_y, 1))
                self._candidates[key] = [1, mm_x, mm_y]
                matched.add(key)
            else:
                # Same candidate seen again: keep it only if it stayed put.
                count, kx, ky = self._candidates.pop(best_key)
                count += 1
                kx = kx + (mm_x - kx) * 0.3   # gently track its centroid
                ky = ky + (mm_y - ky) * 0.3
                key = (round(kx, 1), round(ky, 1))
                self._candidates[key] = [count, kx, ky]
                matched.add(key)

        # Strict consecutive frames: drop anything not seen again this frame.
        for key in [k for k in self._candidates if k not in matched]:
            del self._candidates[key]

        new_holes = []
        for key, (count, kx, ky) in list(self._candidates.items()):
            if count >= config.MIN_HOLE_PERSIST_FRAMES:
                hole = (round(kx, 1), round(ky, 1))
                self.holes.append(hole)
                new_holes.append(hole)
                del self._candidates[key]
                self._heal_reference(frame, hole, side)
                self.cooldown = config.SHOT_COOLDOWN_FRAMES

        # Gently adapt the reference to lighting drift when nothing changed.
        if not changed:
            self._reference = self._reference * 0.98 + frame * 0.02
        self.last_frame = warped_gray
        self.last_overlay = self.draw_overlay(warped_gray, self.holes)
        return new_holes

    def _heal_reference(self, frame, hole_mm, side):
        """Paint the confirmed hole into the reference so it stops diffing."""
        s = self.cal.scale_px_per_mm
        cx = int(hole_mm[0] * s + side / 2.0)
        cy = int(hole_mm[1] * s + side / 2.0)
        r = max(int(config.MAX_HOLE_RADIUS_MM * s) + 2, 4)
        y0, y1 = max(0, cy - r), min(side, cy + r + 1)
        x0, x1 = max(0, cx - r), min(side, cx + r + 1)
        patch = frame[y0:y1, x0:x1]
        color = float(np.mean(patch)) if patch.size else float(frame[cy, cx])
        cv2.circle(self._reference, (cx, cy), r, color, -1)

    def _is_known(self, mm_x, mm_y):
        for hx, hy in self.holes:
            if ((hx - mm_x) ** 2 + (hy - mm_y) ** 2) ** 0.5 < config.HOLE_MIN_SEPARATION_MM:
                return True
        return False

    # ------------------------------------------------------------- output --
    def draw_overlay(self, warped_gray, holes):
        """Return a BGR overlay of the warped target with rings and holes."""
        bgr = cv2.cvtColor(np.asarray(warped_gray, dtype=np.uint8), cv2.COLOR_GRAY2BGR)
        s = self.cal.scale_px_per_mm
        side = bgr.shape[0]
        c = side // 2
        # centre crosshair
        cv2.line(bgr, (c - 40, c), (c + 40, c), (0, 255, 0), 1)
        cv2.line(bgr, (c, c - 40), (c, c + 40), (0, 255, 0), 1)
        # scoring rings (perfect circles in the warped view)
        for rr in config.RING_RADII_MM.values():
            cv2.circle(bgr, (c, c), max(int(rr * s), 1), (0, 255, 255), 1)
        cv2.circle(bgr, (c, c),
                   max(int(config.INNER_TEN_RADIUS_MM * s), 1), (0, 0, 255), 2)
        cv2.circle(bgr, (c, c),
                   max(int(config.BLACK_AREA_DIAMETER_MM / 2 * s), 1), (0, 255, 0), 2)
        for mm_x, mm_y in holes:
            cx = int(mm_x * s + c)
            cy = int(mm_y * s + c)
            cv2.circle(bgr, (cx, cy), max(int(2.25 * s), 3), (0, 0, 255), 2)
            cv2.line(bgr, (cx - 6, cy), (cx + 6, cy), (0, 0, 255), 1)
            cv2.line(bgr, (cx, cy - 6), (cx, cy + 6), (0, 0, 255), 1)
        return bgr


def generate_synthetic_target(side=400, holes_mm=(), cal=None):
    """Build a synthetic fronto-parallel target for offline testing.

    Draws black rings (4-10), white rings (1-3) and punches holes.
    Returns (warped_gray, calibration).
    """
    img = np.full((side, side), 255, dtype=np.uint8)
    cv2.circle(img, (side // 2, side // 2), int(side / 2), 200, -1)  # card
    from config import RING_RADII_MM
    scale = (side / 2) / (RING_RADII_MM[1] + 8)
    px_per_mm = scale
    # black area 4-10
    black_radius_px = RING_RADII_MM[4] * scale
    cv2.circle(img, (side // 2, side // 2), int(black_radius_px), 0, -1)
    # ring lines
    cv2.circle(img, (side // 2, side // 2), int(RING_RADII_MM[10] * scale), 255, 1)
    cv2.circle(img, (side // 2, side // 2), int(RING_RADII_MM[9] * scale), 255, 1)
    cv2.circle(img, (side // 2, side // 2), int(RING_RADII_MM[8] * scale), 255, 1)
    cv2.circle(img, (side // 2, side // 2), int(RING_RADII_MM[7] * scale), 255, 1)
    cv2.circle(img, (side // 2, side // 2), int(RING_RADII_MM[6] * scale), 255, 1)
    cv2.circle(img, (side // 2, side // 2), int(RING_RADII_MM[5] * scale), 255, 1)
    cv2.circle(img, (side // 2, side // 2), int(RING_RADII_MM[4] * scale), 0, 2)
    cv2.circle(img, (side // 2, side // 2), int(RING_RADII_MM[3] * scale), 0, 2)
    cv2.circle(img, (side // 2, side // 2), int(RING_RADII_MM[2] * scale), 0, 2)
    cv2.circle(img, (side // 2, side // 2), int(RING_RADII_MM[1] * scale), 0, 2)
    # punch holes (dark, ~4.5mm)
    for mx, my in holes_mm:
        cx = int(side / 2 + mx * scale)
        cy = int(side / 2 + my * scale)
        r = max(int(2.25 * scale), 3)
        cv2.circle(img, (cx, cy), r, 40, -1)
        cv2.circle(img, (cx, cy), r + 1, 90, 1)

    from app.calibration import Calibration
    cal = cal or Calibration(side / 2, side / 2, side / 2 - 2, side / 2 - 2, 0, px_per_mm)
    return img, cal