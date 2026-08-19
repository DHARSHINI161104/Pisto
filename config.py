"""Central configuration for the rifle score display unit."""

import os

# Project root (parent of this file).
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# --- ISSF 10m Air Rifle target geometry (all diameters in millimetres) ---
# Ring diameters, from ISSF rules for 10m air rifle paper targets.
RING_DIAMETERS_MM = {
    10: 11.5,     # 10 ring
    9: 27.5,
    8: 43.5,
    7: 59.5,
    6: 75.5,
    5: 91.5,
    4: 107.5,
    3: 123.5,
    2: 139.5,
    1: 155.5,
}
INNER_TEN_DIAMETER_MM = 5.0     # the X ring
TARGET_OUTER_DIAMETER_MM = 170.0  # printed card size
BLACK_AREA_DIAMETER_MM = 107.5   # black covers rings 4-10

# Derived radii (mm) used by the scoring engine. Outer -> inner order for lookup.
RING_RADII_MM = {r: d / 2.0 for r, d in RING_DIAMETERS_MM.items()}
INNER_TEN_RADIUS_MM = INNER_TEN_DIAMETER_MM / 2.0

# A shot centre further than this from the target centre is a miss (0.0).
# Ring 1 outer edge = 77.75mm; anything on/outside the 1-ring line is 0.
MAX_SCORING_RADIUS_MM = RING_RADII_MM[1]

# --- Competition format ---
SHOTS_PER_GAME = 10
SHOTS_PER_SERIES = 10           # displayed in groups of 10 on the scoreboard

# --- Preprocessing ---
# Gaussian blur applied to frames before thresholding (calibration) and before
# the background difference (shot detection). Kernel must be odd; sigma 0 asks
# OpenCV to derive sigma from the kernel.
GAUSSIAN_KERNEL = (5, 5)
GAUSSIAN_SIGMA = 0.0

# --- Detection / calibration ---
MIN_HOLE_AREA_MM2 = 6.0         # ~ a 4.5mm pellet hole
MIN_HOLE_RADIUS_MM = 1.4
MAX_HOLE_RADIUS_MM = 4.0
HOLE_MIN_SEPARATION_MM = 3.0    # ignore blobs closer than this to a known hole
DIFF_THRESHOLD = 30             # greyscale difference to count as a change
MIN_HOLE_PERSIST_FRAMES = 3     # a candidate must be seen this many frames
HOUGH_EDGE_LOW = 60
HOUGH_EDGE_HIGH = 150

# --- Calibration stage ---
# The target must be detected on this many consecutive frames with a similar
# centre/scale before calibration is accepted and live scoring starts.
CALIB_MIN_FRAMES = 5
CALIB_CENTER_TOLERANCE_PX = 15  # max frame-to-frame centre drift (px)
CALIB_SCALE_TOLERANCE = 0.08    # max relative scale drift between frames
CALIB_MIN_ASPECT = 0.45         # reject fits that are too skewed (bad angle)
# Frames blended into the detection baseline after calibration; during this
# warm-up no shots are scored (lets the image settle before waiting for a shot).
DETECTOR_WARMUP_FRAMES = 8

# --- Camera ---
CAMERA_SOURCE = 0               # OpenCV index for USB webcams
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
CAMERA_FPS = 20

# --- Server ---
HOST = "0.0.0.0"
PORT = 5000
DEBUG = False

# --- Results export ---
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")  # daily results files
