import pytest

from app.scoring import (score_from_distance, score_for_offset,
                         is_inner_ten, ring_band_width)


def test_inner_ten_is_109():
    assert score_from_distance(0.0) == 10.9
    assert score_from_distance(2.5) == 10.9
    assert is_inner_ten(2.5) is True


def test_ten_ring_decimals():
    # 10-ring annulus (2.5..5.75) holds 9 bands of 0.3611mm each (10.8..10.0).
    assert score_from_distance(2.6) == 10.8
    assert score_from_distance(3.0) == 10.7
    assert score_from_distance(4.0) == 10.4
    assert score_from_distance(5.0) == 10.2
    assert score_from_distance(5.7) == 10.0
    assert score_from_distance(5.75) == 10.0


def test_nine_ring_decimals():
    # 9-ring: 5.75..13.75, band width 0.8mm.
    assert score_from_distance(6.0) == 9.9
    assert score_from_distance(9.0) == 9.5
    assert score_from_distance(13.0) == 9.0


def test_low_rings():
    assert score_from_distance(30.0) == 6.9
    assert score_from_distance(46.0) == 4.9
    assert score_from_distance(54.0) == 3.9
    assert score_from_distance(70.0) == 1.9
    assert score_from_distance(77.5) == 1.0


def test_miss():
    assert score_from_distance(77.8) == 0.0
    assert score_from_distance(200.0) == 0.0
    assert score_from_distance(-5) == 10.9


def test_offset():
    assert score_for_offset(0.0, 0.0) == 10.9
    # (10, 0) -> d=10 -> in the 9-ring -> 9.4.
    assert score_for_offset(10.0, 0.0) == 9.4


def test_band_width_sane():
    assert ring_band_width(10) == pytest.approx((5.75 - 2.5) / 9)
    assert ring_band_width(9) == pytest.approx(0.8)