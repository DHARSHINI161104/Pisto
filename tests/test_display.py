"""Tests for the electronic scoring display: SVG target renderer and routes."""

import pytest

import config
from app import state
from app.target_view import target_display_svg, target_svg
from app.server import create_app


def test_target_display_svg_geometry_and_markers():
    shots = [
        {"shot_no": 1, "x_mm": 10.0, "y_mm": 0.0, "score": 9.4},
        {"shot_no": 2, "x_mm": -6.0, "y_mm": -8.0, "score": 9.4},
    ]
    svg = target_display_svg(shots, current_shot_no=2)

    # Geometry comes from the same config the scoring engine uses.
    assert 'id="geometry"' in svg
    for r in config.RING_RADII_MM.values():
        assert f'r="{r:.2f}"' in svg or f'r="{r:.2f}' in svg
    assert f'r="{config.INNER_TEN_RADIUS_MM:.2f}"' in svg

    # Marker layer present; current shot distinguished from previous.
    assert 'id="markers"' in svg
    assert 'class="marker-current"' in svg
    assert 'class="marker-prev"' in svg

    # Shot (10, 0) on a 170mm card sits at (95.00, 85.00).
    assert 'cx="95.00" cy="85.00"' in svg
    # Current shot (-6, -8) sits at (79.00, 77.00).
    assert 'cx="79.00" cy="77.00"' in svg


def test_display_svg_handles_missing_coordinates():
    svg = target_display_svg([{"shot_no": 1, "x_mm": None, "y_mm": None, "score": 9.0}])
    assert 'id="markers"' in svg
    assert 'marker-current' not in svg  # no marker drawn for missing coords


def test_print_target_svg_still_builds():
    assert "<svg" in target_svg()
    assert "<text" in target_svg()


def test_display_route_returns_200():
    app = create_app()
    client = app.test_client()
    resp = client.get("/display")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'id="markers"' in html
    assert 'id="total"' in html
    assert "Show Camera" in html


def test_api_state_returns_200_with_display_fields():
    app = create_app()
    client = app.test_client()
    js = client.get("/api/state").get_json()
    assert js is not None
    for key in ("shots", "current_shot", "status", "session",
                "target_detected", "calibration_complete", "camera"):
        assert key in js