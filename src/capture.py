import ctypes
import ctypes.wintypes
import numpy as np
import win32gui
import win32ui
import mss


# PrintWindow flags
_PW_CLIENTONLY        = 0x1
_PW_RENDERFULLCONTENT = 0x2  # 要求 DWM 提供完整内容，窗口被遮挡时仍有效（Win8.1+）


class WindowCapture:
    def __init__(self, window_title: str):
        self.window_title = window_title
        self.hwnd = self._find_hwnd()
        self._sct = mss.mss()

    def _find_hwnd(self) -> int:
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
        if not self.is_window_found():
            self.refresh_hwnd()
            if not self.is_window_found():
                return None

        # 优先使用 PrintWindow（后台可用）；失败则降级到 mss（需窗口可见）
        frame = self._printwindow_capture()
        if frame is None:
            frame = self._mss_capture()
        if frame is None:
            return None

        if region is None:
            return frame

        h, w = frame.shape[:2]
        x1 = int(region[0] * w)
        y1 = int(region[1] * h)
        x2 = int(region[2] * w)
        y2 = int(region[3] * h)
        return frame[y1:y2, x1:x2]

    def _printwindow_capture(self) -> np.ndarray | None:
        """
        通过 PrintWindow + PW_RENDERFULLCONTENT 截取窗口客户区。
        DWM 会提供合成缓冲区，即使窗口被其他窗口完全遮挡也能正确截图。
        适用于 DirectX 窗口模式游戏（Unity / Unreal 等）。
        """
        try:
            cr = win32gui.GetClientRect(self.hwnd)
            w, h = cr[2], cr[3]
            if w == 0 or h == 0:
                return None

            hdc = win32gui.GetDC(self.hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hdc)
            mem_dc = mfc_dc.CreateCompatibleDC()
            bmp = win32ui.CreateBitmap()
            bmp.CreateCompatibleBitmap(mfc_dc, w, h)
            mem_dc.SelectObject(bmp)

            ok = ctypes.windll.user32.PrintWindow(
                self.hwnd,
                mem_dc.GetSafeHdc(),
                _PW_CLIENTONLY | _PW_RENDERFULLCONTENT,
            )

            frame = None
            if ok:
                raw = bmp.GetBitmapBits(True)
                img = np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 4)
                frame = img[:, :, :3].copy()  # BGRA → BGR，copy 脱离 bitmap 生命周期

            mem_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(self.hwnd, hdc)
            win32gui.DeleteObject(bmp.GetHandle())
            return frame
        except Exception:
            return None

    def _mss_capture(self) -> np.ndarray | None:
        """mss 截图（降级方案，需要窗口在屏幕上可见且未被遮挡）。"""
        try:
            client_rect = win32gui.GetClientRect(self.hwnd)
            cw, ch = client_rect[2], client_rect[3]
            if cw == 0 or ch == 0:
                return None

            pt = ctypes.wintypes.POINT(0, 0)
            ctypes.windll.user32.ClientToScreen(self.hwnd, ctypes.byref(pt))

            monitor = {"left": pt.x, "top": pt.y, "width": cw, "height": ch}
            sct_img = self._sct.grab(monitor)
            return np.array(sct_img)[:, :, :3]
        except Exception:
            return None
