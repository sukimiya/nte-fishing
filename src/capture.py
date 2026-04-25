import ctypes
import ctypes.wintypes
import logging
import threading
import numpy as np
import win32gui
import mss
from windows_capture import WindowsCapture as _WGCapture, Frame, InternalCaptureControl

log = logging.getLogger(__name__)


class WindowCapture:
    """
    优先使用 Windows Graphics Capture API（WGC）截图：
    即使游戏窗口被其他窗口完全遮挡或不在前台，也能正确截取 DX 渲染内容。
    WGC 不可用时降级为 mss（需要窗口可见）。
    """

    def __init__(self, window_title: str):
        self.window_title = window_title
        self.hwnd = self._find_hwnd()

        self._lock = threading.Lock()
        self._latest_frame: np.ndarray | None = None
        self._capture_ctrl = None

        self._sct = mss.mss()          # mss 降级备用
        self._start_wgc()

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

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
            # 窗口重新找到后重启 WGC
            self._start_wgc()

        with self._lock:
            frame = self._latest_frame

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

    # ------------------------------------------------------------------
    # WGC 初始化
    # ------------------------------------------------------------------

    def _start_wgc(self):
        if not self.is_window_found():
            return
        try:
            cap = _WGCapture(
                cursor_capture=False,
                draw_border=False,
                window_hwnd=self.hwnd,
            )

            @cap.event
            def on_frame_arrived(frame: Frame, ctrl: InternalCaptureControl):
                # frame_buffer 是 BGRA numpy 数组
                bgr = frame.frame_buffer[:, :, :3].copy()
                with self._lock:
                    self._latest_frame = bgr

            @cap.event
            def on_closed():
                log.debug("WGC 会话关闭")

            # start() 是阻塞的，放到 daemon 线程运行
            t = threading.Thread(target=cap.start, daemon=True, name="wgc-capture")
            t.start()
            self._capture_ctrl = cap
            log.info("WGC 截图已启动（后台，hwnd=%d）", self.hwnd)
        except Exception as e:
            log.warning("WGC 初始化失败，降级为 mss: %s", e)
            self._capture_ctrl = None

    # ------------------------------------------------------------------
    # mss 降级方案
    # ------------------------------------------------------------------

    def _mss_capture(self) -> np.ndarray | None:
        """mss 截图（需要窗口在屏幕上可见且未被遮挡）。"""
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

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _find_hwnd(self) -> int:
        result = [0]
        def cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and self.window_title in win32gui.GetWindowText(hwnd):
                result[0] = hwnd
        win32gui.EnumWindows(cb, None)
        return result[0]
