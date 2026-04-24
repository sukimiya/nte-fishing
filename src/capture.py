import numpy as np
import win32gui
import win32ui
import win32con
from PIL import Image


class WindowCapture:
    def __init__(self, window_title: str):
        self.window_title = window_title
        self.hwnd = win32gui.FindWindow(None, window_title)

    def is_window_found(self) -> bool:
        return self.hwnd != 0

    def refresh_hwnd(self):
        self.hwnd = win32gui.FindWindow(None, self.window_title)

    def get_window_size(self) -> tuple[int, int]:
        if not self.is_window_found():
            return (0, 0)
        rect = win32gui.GetClientRect(self.hwnd)
        return (rect[2], rect[3])

    def get_frame(self, region: tuple[float, float, float, float] | None = None) -> np.ndarray | None:
        """
        截取游戏窗口画面，无需游戏在前台。
        region: (x_start%, y_start%, x_end%, y_end%)，不传则截取整个窗口。
        返回 BGR numpy 数组，失败返回 None。
        """
        if not self.is_window_found():
            self.refresh_hwnd()
            if not self.is_window_found():
                return None

        full = self._bitblt_capture()
        if full is None:
            return None

        if region is None:
            return full

        h, w = full.shape[:2]
        x1 = int(region[0] * w)
        y1 = int(region[1] * h)
        x2 = int(region[2] * w)
        y2 = int(region[3] * h)
        return full[y1:y2, x1:x2]

    def _bitblt_capture(self) -> np.ndarray | None:
        """使用 BitBlt 从游戏 DC 截图（无需前台），返回 BGR numpy 数组。"""
        try:
            rect = win32gui.GetClientRect(self.hwnd)
            w, h = rect[2], rect[3]
            if w == 0 or h == 0:
                return None

            hwnd_dc = win32gui.GetWindowDC(self.hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()

            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
            save_dc.SelectObject(bitmap)
            save_dc.BitBlt((0, 0), (w, h), mfc_dc, (0, 0), win32con.SRCCOPY)

            bmp_info = bitmap.GetInfo()
            bmp_str = bitmap.GetBitmapBits(True)
            img = Image.frombuffer(
                'RGB',
                (bmp_info['bmWidth'], bmp_info['bmHeight']),
                bmp_str, 'raw', 'BGRX', 0, 1
            )
            frame = np.array(img)[:, :, :3]
            frame = frame[:, :, ::-1].copy()  # RGB → BGR

            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(self.hwnd, hwnd_dc)
            win32gui.DeleteObject(bitmap.GetHandle())

            return frame
        except Exception:
            return None
