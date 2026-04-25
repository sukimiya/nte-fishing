import numpy as np
import win32gui
import mss


class WindowCapture:
    def __init__(self, window_title: str):
        self.window_title = window_title
        self.hwnd = self._find_hwnd()
        self._sct = mss.MSS()

    def _find_hwnd(self) -> int:
        """查找标题中包含 window_title 的可见窗口，返回 hwnd，找不到返回 0。"""
        result = [0]
        def cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                t = win32gui.GetWindowText(hwnd)
                if self.window_title in t:
                    result[0] = hwnd
        win32gui.EnumWindows(cb, None)
        return result[0]

    def is_window_found(self) -> bool:
        return self.hwnd != 0

    def refresh_hwnd(self):
        self.hwnd = self._find_hwnd()

    def get_window_size(self) -> tuple[int, int]:
        if not self.is_window_found():
            return (0, 0)
        rect = win32gui.GetClientRect(self.hwnd)
        return (rect[2], rect[3])

    def get_frame(self, region: tuple[float, float, float, float] | None = None) -> np.ndarray | None:
        """
        截取游戏窗口画面（基于屏幕坐标，无需游戏在前台）。
        region: (x_start%, y_start%, x_end%, y_end%)，不传则截取整个窗口客户区。
        返回 BGR numpy 数组，失败返回 None。
        注意：游戏窗口不应被其他窗口遮挡，否则会捕获到遮挡内容。
        """
        if not self.is_window_found():
            self.refresh_hwnd()
            if not self.is_window_found():
                return None

        full = self._mss_capture()
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

    def _mss_capture(self) -> np.ndarray | None:
        """
        用 mss 截取游戏窗口在屏幕上的区域，返回 BGR numpy 数组。
        通过 GetWindowRect 获取屏幕坐标，再用 GetClientRect + ClientToScreen
        精确定位客户区（排除标题栏和边框）。
        """
        try:
            # 窗口边框矩形（屏幕坐标）
            win_rect = win32gui.GetWindowRect(self.hwnd)
            # 客户区矩形（窗口本地坐标）
            client_rect = win32gui.GetClientRect(self.hwnd)
            cw, ch = client_rect[2], client_rect[3]
            if cw == 0 or ch == 0:
                return None

            # 客户区左上角的屏幕坐标 = 窗口左上 + 标题栏/边框偏移
            import ctypes
            pt = ctypes.wintypes.POINT(0, 0)
            ctypes.windll.user32.ClientToScreen(self.hwnd, ctypes.byref(pt))
            cx, cy = pt.x, pt.y

            monitor = {"left": cx, "top": cy, "width": cw, "height": ch}
            sct_img = self._sct.grab(monitor)

            # mss 返回 BGRA，转为 BGR
            frame = np.array(sct_img)[:, :, :3]
            return frame
        except Exception:
            return None
