# tests/test_controller.py
import sys
import types
import pytest
from unittest.mock import patch, MagicMock

# Mock win32api 和 win32con 在 import controller 之前
_mock_win32api = MagicMock()
_mock_win32api.MapVirtualKey.return_value = 0
sys.modules['win32api'] = _mock_win32api
sys.modules['win32con'] = MagicMock()

from src.controller import FishingController


@pytest.fixture
def controller():
    return FishingController(hwnd=12345)


def test_adjust_line_positive_error_presses_a(controller):
    """error > DEAD_ZONE → press 'A' (move player left)"""
    with patch.object(controller, '_press_key') as mock_press:
        controller.adjust_line(error=+100)
        mock_press.assert_called_once()
        key, duration = mock_press.call_args[0]
        assert key == 'a'
        assert 0.01 <= duration <= 0.15


def test_adjust_line_negative_error_presses_d(controller):
    """error < -DEAD_ZONE → press 'D' (move player right)"""
    with patch.object(controller, '_press_key') as mock_press:
        controller.adjust_line(error=-80)
        mock_press.assert_called_once()
        key, duration = mock_press.call_args[0]
        assert key == 'd'
        assert 0.01 <= duration <= 0.15


def test_adjust_line_within_dead_zone_no_press(controller):
    """error within DEAD_ZONE → no key press"""
    with patch.object(controller, '_press_key') as mock_press:
        controller.adjust_line(error=5)
        mock_press.assert_not_called()


def test_key_duration_proportional_to_error(controller):
    """larger error → longer press (up to max)"""
    with patch.object(controller, '_press_key') as mock_press:
        controller.adjust_line(error=50)
        _, dur50 = mock_press.call_args[0]
        mock_press.reset_mock()
        controller.adjust_line(error=100)
        _, dur100 = mock_press.call_args[0]
    assert dur100 > dur50


def test_press_cast_sends_f_key(controller):
    with patch.object(controller, '_press_key') as mock_press:
        controller.press_cast()
        mock_press.assert_called_once_with('f', 0.05)
