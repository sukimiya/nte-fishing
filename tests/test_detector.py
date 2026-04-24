# tests/test_detector.py
import cv2
import numpy as np
import pytest
from src.detector import StateDetector, GameState

FRAMES = {
    'idle':      'frames/bite_f2950.png',
    'bite':      'frames/bite_f3050.png',
    'fishing_3': 'frames/v1_f03_374.png',
    'fishing_4': 'frames/v1_f04_481.png',
    'fishing_5': 'frames/v1_f05_587.png',
    'fishing_6': 'frames/v1_f06_694.png',
}


@pytest.fixture
def detector():
    return StateDetector()


def test_detect_idle_state(detector):
    frame = cv2.imread(FRAMES['idle'])
    assert detector.detect_state(frame) == GameState.IDLE


def test_detect_bite_state(detector):
    frame = cv2.imread(FRAMES['bite'])
    assert detector.detect_state(frame) == GameState.BITE


@pytest.mark.parametrize("key", ['fishing_3', 'fishing_4', 'fishing_5', 'fishing_6'])
def test_detect_fishing_state(detector, key):
    frame = cv2.imread(FRAMES[key])
    assert detector.detect_state(frame) == GameState.FISHING


def test_detect_fishing_positions_in_range(detector):
    frame = cv2.imread(FRAMES['fishing_3'])
    fl, fr, px = detector.detect_fishing_positions(frame)
    assert fl is not None and fr is not None and px is not None
    assert fl < fr
    assert fl - 200 < px < fr + 200


@pytest.mark.parametrize("key,expected_error_sign", [
    ('fishing_3', +1),
    ('fishing_4',  0),
])
def test_fishing_error_sign(detector, key, expected_error_sign):
    frame = cv2.imread(FRAMES[key])
    fl, fr, px = detector.detect_fishing_positions(frame)
    fish_center = (fl + fr) / 2
    error = px - fish_center
    if expected_error_sign == +1:
        assert error > 10
    elif expected_error_sign == 0:
        assert abs(error) < 50
