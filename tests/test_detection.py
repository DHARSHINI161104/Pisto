import config
from app.detection import ShotDetector, generate_synthetic_target
from app.scoring import score_from_distance


def _fresh_detector(cal, img):
    det = ShotDetector(cal)
    det.set_reference(img)
    for _ in range(config.DETECTOR_WARMUP_FRAMES + 1):
        det.update(img)
    return det


def _holes_at(*mm_positions, side=400):
    img, cal = generate_synthetic_target(side=side, holes_mm=[])
    det = ShotDetector(cal)
    det.set_reference(img)
    # Let the warm-up blend the clean target into the baseline.
    for _ in range(config.DETECTOR_WARMUP_FRAMES + 1):
        det.update(img)
    found = []
    for _ in range(8):
        img2, _ = generate_synthetic_target(side=side, holes_mm=mm_positions)
        new = det.update(img2)
        found.extend(new)
        if len(found) >= len(mm_positions):
            break
    return found, cal


def test_no_holes_detected():
    img, cal = generate_synthetic_target(side=400, holes_mm=[])
    det = ShotDetector(cal)
    det.set_reference(img)
    for _ in range(config.DETECTOR_WARMUP_FRAMES + 3):
        assert det.update(img) == []


def test_capture_scores_single_frame():
    """Manual (Enter-key) capture scores a hole from a single frame."""
    img, cal = generate_synthetic_target(side=400, holes_mm=[])
    det = ShotDetector(cal)
    det.set_reference(img)
    for _ in range(config.DETECTOR_WARMUP_FRAMES + 1):
        det.update(img)
    shot_img, _ = generate_synthetic_target(side=400, holes_mm=[(8.0, 0.0)])
    new = det.capture(shot_img)
    assert len(new) == 1
    assert abs(new[0][0] - 8.0) < 1.0 and abs(new[0][1]) < 1.0
    # The same frame must not re-score the hole.
    assert det.capture(shot_img) == []


def test_capture_never_scores_known_holes():
    """A hole already on the reference must be ignored by capture()."""
    img, cal = generate_synthetic_target(side=400, holes_mm=[(5.0, 5.0)])
    det = ShotDetector(cal)
    det.set_reference(img)
    for _ in range(config.DETECTOR_WARMUP_FRAMES + 1):
        det.update(img)
    assert det.capture(img) == []


def test_single_hole_detected_and_scored():
    target = (8.0, 0.0)   # d=8 -> 9.7 by scoring
    found, cal = _holes_at(target)
    assert len(found) == 1
    d = (found[0][0] ** 2 + found[0][1] ** 2) ** 0.5
    assert 7.0 < d < 9.0
    assert 9.5 <= score_from_distance(d) <= 9.8


def test_multiple_holes():
    positions = [(0.0, 0.0), (12.0, 5.0), (-9.0, -3.0), (30.0, 15.0)]
    found, cal = _holes_at(*positions)
    assert len(found) >= 3
    for fx, fy in found:
        assert any((abs(fx - px) < 3 and abs(fy - py) < 3) for px, py in positions)


def test_deduplication_no_dupes():
    img, cal = generate_synthetic_target(side=400, holes_mm=[(5.0, 5.0)])
    det = ShotDetector(cal)
    det.set_reference(img)
    for _ in range(config.DETECTOR_WARMUP_FRAMES + 3):
        det.update(img)          # same image repeatedly -> no new holes
    assert det.holes == []
    for _ in range(6):
        assert det.update(img) == []


def test_warmup_ignores_immediate_changes():
    img, cal = generate_synthetic_target(side=400, holes_mm=[])
    det = ShotDetector(cal)
    det.set_reference(img)
    img2, _ = generate_synthetic_target(side=400, holes_mm=[(5.0, 0.0)])
    for _ in range(config.DETECTOR_WARMUP_FRAMES):
        # A hole appearing during warm-up must NOT be scored.
        assert det.update(img2) == []
    assert det.holes == []


def test_jittering_blob_is_not_scored():
    """A blob that wanders more than SHOT_TRACK_RADIUS_MM each frame must never
    confirm - this is what caused endless false shots from camera noise."""
    img, cal = generate_synthetic_target(side=400, holes_mm=[])
    det = _fresh_detector(cal, img)
    step = config.SHOT_TRACK_RADIUS_MM + 1.0
    for i in range(15):
        pos = (5.0 + i * step, 0.0)
        frame, _ = generate_synthetic_target(side=400, holes_mm=[pos])
        assert det.update(frame) == []
    assert det.holes == []


def test_non_consecutive_appearance_is_not_scored():
    """A blob that flickers on/off must not accumulate toward a shot."""
    img, cal = generate_synthetic_target(side=400, holes_mm=[])
    det = _fresh_detector(cal, img)
    pos = (8.0, 4.0)
    hole_img, _ = generate_synthetic_target(side=400, holes_mm=[pos])
    for _ in range(20):
        det.update(hole_img)          # present
        det.update(img)               # absent next frame
    assert det.holes == []


def test_cooldown_blocks_shot_during_reload():
    """After one shot, a new change during the cooldown must NOT be scored."""
    img, cal = generate_synthetic_target(side=400, holes_mm=[])
    det = _fresh_detector(cal, img)

    hole1_img, _ = generate_synthetic_target(side=400, holes_mm=[(8.0, 0.0)])
    new = []
    for _ in range(config.MIN_HOLE_PERSIST_FRAMES):
        new.extend(det.update(hole1_img))
    assert len(new) == 1
    assert det.cooldown > 0

    # A new hole appears during the reload interval -> ignored. The clean
    # target is still being watched (only the first hole is on it).
    hole2_img, _ = generate_synthetic_target(side=400, holes_mm=[(-8.0, -8.0)])
    during = []
    for _ in range(config.SHOT_COOLDOWN_FRAMES):
        during.extend(det.update(img))
    assert during == []
    assert len(det.holes) == 1
    assert abs(det.holes[0][0] - 8.0) < 1.0 and abs(det.holes[0][1]) < 1.0

    # After the cooldown, the new hole is scored as the next shot.
    after = []
    for _ in range(config.MIN_HOLE_PERSIST_FRAMES):
        after.extend(det.update(hole2_img))
    assert len(after) == 1
    assert len(det.holes) == 2