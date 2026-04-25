import ctypes
import ctypes.wintypes
import logging
import threading
import cv2
import numpy as np
import win32gui
import mss
from windows_capture import WindowsCapture as _WGCapture, Frame, InternalCaptureControl

log = logging.getLogger(__name__)


class WindowCapture:
    """
    优先使用 Windows Graphics Capture API（WGC）截图：
    即使游戏窗口被其他窗口完全遮挡也能正确截取 DX 渲染内容。
    WGC 帧会 resize 到逻辑像素尺寸（与 DPI 缩放无关），保持检测阈值一致。
    WGC 不可用时降级为 mss（需要窗口可见）。
    """

    def __init__(self, window_title: str):
        self.window_title = window_title
        self.hwnd = self._find_hwnd()
        self._lock = threading.Lock()
        self._latest_frame: np.ndarray | None = None
        self._sct = mss.mss()
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
            self._start_wgc()

        with self._lock:
            frame = self._latest_frame

        if frame is None:
            log.debug("WGC 无帧，降级为 mss")
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

            _first_frame = [True]

            @cap.event
            def on_frame_arrived(frame: Frame, ctrl: InternalCaptureControl):
                try:
                    bgr = frame.frame_buffer[:, :, :3].copy()  # BGRA → BGR

                    # WGC 按物理像素截图（含 DPI 缩放），resize 到逻辑像素尺寸
                    # 保持与 mss 一致，避免 MARKER_MAX_WIDTH 等像素级阈值失效
                    cr = win32gui.GetClientRect(self.hwnd)
                    lw, lh = cr[2], cr[3]
                    if lw > 0 and lh > 0 and (bgr.shape[1] != lw or bgr.shape[0] != lh):
                        bgr = cv2.resize(bgr, (lw, lh), interpolation=cv2.INTER_LINEAR)

                    with self._lock:
                        self._latest_frame = bgr

                    if _first_frame[0]:
                        _first_frame[0] = False
                        log.info("WGC 首帧到达，尺寸 %dx%d（hwnd=%d）", bgr.shape[1], bgr.shape[0], self.hwnd)
                except Exception as e:
                    log.warning("WGC 帧处理失败: %s", e)

            @cap.event
            def on_closed():
                log.warning("WGC 会话关闭（hwnd=%d）", self.hwnd)
                with self._lock:
                    self._latest_frame = None

            def _run():
                try:
                    cap.start()
                except Exception as e:
                    log.warning("WGC cap.start() 异常退出: %s", e)

            t = threading.Thread(target=_run, daemon=True, name="wgc-capture")
            t.start()
            log.info("WGC 截图已启动（hwnd=%d）", self.hwnd)
        except Exception as e:
            log.warning("WGC 初始化失败，降级为 mss: %s", e)

    # ------------------------------------------------------------------
    # mss 降级方案
    # ------------------------------------------------------------------

    def _mss_capture(self) -> np.ndarray | None:
        try:
            cr = win32gui.GetClientRect(self.hwnd)
            cw, ch = cr[2], cr[3]
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

    def _find_hwnd(self) -> int:
        result = [0]
        def cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and self.window_title in win32gui.GetWindowText(hwnd):
                result[0] = hwnd
        win32gui.EnumWindows(cb, None)
        return result[0]
