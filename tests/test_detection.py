import config
from app.detection import ShotDetector, generate_synthetic_target
from app.scoring import score_from_distance


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