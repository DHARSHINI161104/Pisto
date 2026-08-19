"""Render the ISSF 10m air rifle target as SVG (for printing) and provide the
ring geometry the browser uses for click-to-score manual entry."""

from config import (RING_RADII_MM, INNER_TEN_RADIUS_MM, RING_DIAMETERS_MM,
                    TARGET_OUTER_DIAMETER_MM, BLACK_AREA_DIAMETER_MM)

RING_LABELS = {10: "10", 9: "9", 8: "8", 7: "7", 6: "6", 5: "5",
               4: "4", 3: "3", 2: "2", 1: "1"}


def target_geometry():
    """Ring radii in mm, plus the black-area radius and card size."""
    return {
        "radii_mm": {str(r): RING_RADII_MM[r] for r in sorted(RING_RADII_MM, reverse=True)},
        "inner_ten_mm": INNER_TEN_RADIUS_MM,
        "black_mm": BLACK_AREA_DIAMETER_MM / 2.0,
        "card_mm": TARGET_OUTER_DIAMETER_MM / 2.0,
    }


def _svg_circle(cx, cy, radius, stroke, width, fill="none", dash=None):
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{radius:.2f}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"{dash_attr}/>')


def target_svg(page_mm=170.0, label=True):
    """Return an SVG string of a single ISSF target (one per printed page).

    Coordinates are in millimetres so a browser print-out is exact scale.
    """
    r = page_mm / 2.0
    cx = cy = r
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{page_mm}mm" '
             f'height="{page_mm}mm" viewBox="0 0 {page_mm} {page_mm}">']
    parts.append(f'<rect width="{page_mm}" height="{page_mm}" fill="white" '
                 f'stroke="black" stroke-width="0.4"/>')
    # rings 1-3 on white card
    for ring in (3, 2, 1):
        parts.append(_svg_circle(cx, cy, RING_RADII_MM[ring], "black", 0.3))
    # black area (4-10)
    parts.append(_svg_circle(cx, cy, RING_RADII_MM[4], "none", 0, fill="black"))
    # rings drawn on top: white lines inside black, black lines outside
    for ring in (10, 9, 8, 7, 6, 5, 4):
        stroke = "white" if ring >= 4 else "black"
        parts.append(_svg_circle(cx, cy, RING_RADII_MM[ring], stroke, 0.3))
    # inner ten
    parts.append(_svg_circle(cx, cy, INNER_TEN_RADIUS_MM, "white", 0.3))
    if label:
        fs = 4.0
        for ring, radius in RING_RADII_MM.items():
            if ring == 10:
                continue
            mid = (radius + (INNER_TEN_RADIUS_MM if ring == 10 else RING_RADII_MM.get(ring + 1, 0))) / 2.0
            parts.append(
                f'<text x="{cx:.2f}" y="{cy - mid + fs / 3:.2f}" '
                f'font-size="{fs}" text-anchor="middle" fill="white" '
                f'font-family="Arial">{RING_LABELS[ring]}</text>')
    parts.append("</svg>")
    return "".join(parts)


def target_svg_page():
    """Full printable page: one target, one side of the sheet."""
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<title>ISSF 10m Air Rifle Target</title>'
        "<style>body{margin:0;display:flex;align-items:center;justify-content:center;"
        "height:100vh}svg{max-width:100%;max-height:100%}</style></head><body>"
        + target_svg() + "</body></html>"
    )


def _ring_label_positions():
    """(ring, mid_radius_mm) for each ring band, outer->inner band midpoint."""
    radii = {r: RING_RADII_MM[r] for r in sorted(RING_RADII_MM, reverse=True)}
    positions = {}
    for ring in range(10, 0, -1):
        outer = radii[ring]
        inner = INNER_TEN_RADIUS_MM if ring == 10 else radii[ring + 1]
        positions[ring] = (outer + inner) / 2.0
    return positions


def target_display_svg(shots=None, current_shot_no=None, labels=True):
    """Render the live electronic-scoring target with shot markers.

    Drawn in the same millimetre coordinate system the scoring engine uses:
    the target centre is at (card/2, card/2), a shot with offset (x_mm, y_mm)
    from the centre is plotted at (cx + x_mm, cy + y_mm). Ring radii come from
    RING_RADII_MM / INNER_TEN_RADIUS_MM (config) - the exact geometry used by
    app.scoring. The marker layer is wrapped in <g id="markers"> so the browser
    can re-render only the shots when new ones arrive via /api/state.
    """
    card = TARGET_OUTER_DIAMETER_MM
    r = card / 2.0
    cx = cy = r
    mid = _ring_label_positions()

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {card} {card}" '
             f'class="target-svg">']
    parts.append('<g id="geometry">')
    # card
    parts.append(f'<rect width="{card}" height="{card}" fill="#f6f7f9" '
                 f'stroke="#9aa4b0" stroke-width="0.3"/>')
    # rings 1-3 on white card
    for ring in (3, 2, 1):
        parts.append(_svg_circle(cx, cy, RING_RADII_MM[ring], "#1a1d21", 0.5))
    # black bull (4-10)
    parts.append(_svg_circle(cx, cy, RING_RADII_MM[4], "none", 0, fill="#101215"))
    # white ring lines inside the black area
    for ring in (10, 9, 8, 7, 6, 5):
        parts.append(_svg_circle(cx, cy, RING_RADII_MM[ring], "#e8edf2", 0.5))
    # ring 4 boundary line (edge of the black bull)
    parts.append(_svg_circle(cx, cy, RING_RADII_MM[4], "#000000", 0.5))
    # inner ten (X)
    parts.append(_svg_circle(cx, cy, INNER_TEN_RADIUS_MM, "#e8edf2", 0.5))

    if labels:
        for ring in range(10, 0, -1):
            m = mid[ring]
            fs = 2.0 if ring == 10 else (2.4 if ring == 9 else 3.0)
            fill = "#e8edf2" if ring >= 4 else "#1a1d21"
            for sgn in (-1, 1):
                x = cx + sgn * m
                parts.append(
                    f'<text x="{x:.2f}" y="{cy:.2f}" font-size="{fs}" '
                    f'text-anchor="middle" dominant-baseline="central" '
                    f'fill="{fill}" font-family="Segoe UI, Arial, sans-serif">'
                    f'{ring}</text>')
    parts.append('</g>')

    parts.append('<g id="markers">')
    for s in shots or []:
        parts.append(_shot_marker(s, s.get("shot_no") == current_shot_no))
    parts.append('</g>')

    parts.append("</svg>")
    return "".join(parts)


def _shot_marker(shot, current):
    """One shot marker: bright crosshair for the current shot, dimmer dot else."""
    x = shot.get("x_mm")
    y = shot.get("y_mm")
    if x is None or y is None:
        return ""
    card = TARGET_OUTER_DIAMETER_MM
    cx = cy = card / 2.0
    px = cx + float(x)
    py = cy + float(y)
    if current:
        return (
            f'<g class="marker-current">'
            f'<circle cx="{px:.2f}" cy="{py:.2f}" r="3.0" fill="rgba(231,76,60,0.35)" '
            f'stroke="#e74c3c" stroke-width="0.8"/>'
            f'<line x1="{px-6:.2f}" y1="{py:.2f}" x2="{px+6:.2f}" y2="{py:.2f}" '
            f'stroke="#e74c3c" stroke-width="0.6"/>'
            f'<line x1="{px:.2f}" y1="{py-6:.2f}" x2="{px:.2f}" y2="{py+6:.2f}" '
            f'stroke="#e74c3c" stroke-width="0.6"/>'
            f'</g>')
    return (f'<g class="marker-prev">'
            f'<circle cx="{px:.2f}" cy="{py:.2f}" r="2.2" '
            f'fill="rgba(46,204,113,0.30)" stroke="#2ecc71" stroke-width="0.5"/>'
            f'</g>')