import pytest
from unittest.mock import patch, MagicMock
import numpy as np


def test_window_not_found_returns_zero_hwnd():
    with patch('win32gui.EnumWindows'):  # EnumWindows 不回调，hwnd 保持 0
        from src.capture import WindowCapture
        cap = WindowCapture("不存在的窗口")
        assert cap.hwnd == 0
        assert not cap.is_window_found()


def test_get_frame_returns_none_when_no_window():
    with patch('win32gui.EnumWindows'):
        from src.capture import WindowCapture
        cap = WindowCapture("不存在的窗口")
        assert cap.get_frame() is None


def test_get_frame_with_region_returns_correct_shape():
    """给定 mock HWND，get_frame with region=(0,0,1,1) 返回完整 ndarray。"""
    mock_array = np.zeros((1440, 2304, 3), dtype=np.uint8)

    def fake_enum(cb, extra):
        # 模拟找到一个 hwnd=12345 的窗口
        with patch('win32gui.IsWindowVisible', return_value=True), \
             patch('win32gui.GetWindowText', return_value="异环"):
            cb(12345, None)

    with patch('win32gui.EnumWindows', side_effect=fake_enum), \
         patch('win32gui.GetClientRect', return_value=(0, 0, 2304, 1440)), \
         patch('src.capture.WindowCapture._mss_capture', return_value=mock_array):
        from src.capture import WindowCapture
        cap = WindowCapture("异环")
        frame = cap.get_frame(region=(0.0, 0.0, 1.0, 1.0))
        assert frame is not None
        assert frame.shape == (1440, 2304, 3)
