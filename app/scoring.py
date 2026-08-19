"""ISSF 10m air rifle decimal scoring.

A pellet's *centre* distance from the target centre (in mm) is converted to a
decimal score (0.0 .. 10.9).

Convention used (matches common electronic-scoring behaviour):

* centre within the inner-ten (X, radius 2.5mm)  -> 10.9
* the 10-ring annulus (X to the 10-ring line) is divided into 9 bands:
  10.8 (innermost) .. 10.0 (outermost), so the 10-ring has 10 levels total
* every other ring is divided radially into 10 equal bands: the band closest
  to the centre scores N.9, the outermost band scores N.0
* anything whose centre is outside the 1-ring line scores 0.0
"""

from config import RING_RADII_MM, INNER_TEN_RADIUS_MM, MAX_SCORING_RADIUS_MM

# Radii ordered from the 10 ring outward; ring N sits between RING_RADII[N]
# and RING_RADII[N-1]'s band layout is defined in the module docstring.
RADII_BY_RING = {r: RING_RADII_MM[r] for r in sorted(RING_RADII_MM, reverse=True)}


def ring_band_width(ring: int) -> float:
    """Radial width of one decimal band.

    The 10-ring annulus (between the X ring and the 10-ring line) holds 9
    decimal bands; every other ring holds 10.
    """
    outer = RADII_BY_RING[ring]
    if ring == 10:
        return (outer - INNER_TEN_RADIUS_MM) / 9.0
    return (outer - RADII_BY_RING[ring + 1]) / 10.0


def is_inner_ten(d_mm: float) -> bool:
    """True when the centre distance is inside the X (inner-ten) ring."""
    return d_mm <= INNER_TEN_RADIUS_MM


def score_from_distance(d_mm: float) -> float:
    """Return the decimal score for a shot whose centre is d_mm from centre.

    Scores 0.0 (miss) up to 10.9 (inner ten). Float input is clipped at 0.
    """
    if d_mm < 0:
        d_mm = 0.0
    if d_mm > MAX_SCORING_RADIUS_MM:
        return 0.0
    if is_inner_ten(d_mm):
        return 10.9

    for ring in range(10, 0, -1):
        outer = RADII_BY_RING[ring]
        if d_mm <= outer:
            if ring == 10:
                # 10-ring annulus holds 9 decimal bands (10.8..10.0);
                # 10.9 is the X (inner-ten) ring itself.
                inner = INNER_TEN_RADIUS_MM
                band_w = (outer - inner) / 9.0
                top = 8
            else:
                inner = RADII_BY_RING[ring + 1]
                band_w = (outer - inner) / 10.0
                top = 9
            band = int((d_mm - inner) / band_w)
            band = min(band, 9)
            decimal = max(top - band, 0)
            return round(ring + decimal / 10.0, 1)
    return 0.0


def score_for_offset(dx_mm: float, dy_mm: float) -> float:
    """Convenience: score for a shot offset (dx, dy) from centre in mm."""
    d = (dx_mm ** 2 + dy_mm ** 2) ** 0.5
    return score_from_distance(d)


def ring_value(score: float) -> int:
    """Whole-number ring (1..10) for a decimal score, or 0 for a miss."""
    return int(score)
