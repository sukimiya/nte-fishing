import ctypes
import ctypes.wintypes
import logging
import threading
import cv2
import numpy as np
import win32gui
import win32ui
import mss
from windows_capture import WindowsCapture as _WGCapture, Frame, InternalCaptureControl

log = logging.getLogger(__name__)

_WDA_EXCLUDEFROMCAPTURE = 0x00000011
_PW_RENDERFULLCONTENT   = 0x00000002


class WindowCapture:
    """
    截图优先级：
    1. WGC（Windows Graphics Capture）：后台 DX 内容，但被 WDA_EXCLUDEFROMCAPTURE 屏蔽时返回黑帧
    2. PrintWindow(PW_RENDERFULLCONTENT)：不受 WDA_EXCLUDEFROMCAPTURE 限制，无需窗口可见
    3. mss：仅当窗口在屏幕上可见时有效，作为最终兜底
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

        # WGC 黑帧（WDA_EXCLUDEFROMCAPTURE 保护）→ 降级为 PrintWindow
        if frame is not None and frame.mean() < 5:
            log.debug("WGC 返回黑帧（均值=%.2f），疑似 WDA 保护，尝试 PrintWindow", frame.mean())
            frame = None

        if frame is None:
            frame = self._print_window_capture()

        if frame is None:
            log.debug("PrintWindow 无效，降级为 mss")
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
    # WGC
    # ------------------------------------------------------------------

    def _start_wgc(self):
        if not self.is_window_found():
            return

        # 记录 WDA 保护状态，方便诊断
        aff = ctypes.c_uint32(0)
        ctypes.windll.user32.GetWindowDisplayAffinity(self.hwnd, ctypes.byref(aff))
        if aff.value != 0:
            log.warning("窗口 WDA 保护已开启（值=%d），WGC 在后台可能返回黑帧，将自动降级为 PrintWindow", aff.value)
        else:
            log.info("窗口 WDA 保护未开启，WGC 后台截图应正常")

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
                    bgr = frame.frame_buffer[:, :, :3].copy()
                    cr = win32gui.GetClientRect(self.hwnd)
                    lw, lh = cr[2], cr[3]
                    if lw > 0 and lh > 0 and (bgr.shape[1] != lw or bgr.shape[0] != lh):
                        bgr = cv2.resize(bgr, (lw, lh), interpolation=cv2.INTER_LINEAR)
                    with self._lock:
                        self._latest_frame = bgr
                    if _first_frame[0]:
                        _first_frame[0] = False
                        log.info("WGC 首帧到达 %dx%d 均值=%.1f（hwnd=%d）",
                                 bgr.shape[1], bgr.shape[0], bgr.mean(), self.hwnd)
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

            threading.Thread(target=_run, daemon=True, name="wgc-capture").start()
            log.info("WGC 截图已启动（hwnd=%d）", self.hwnd)
        except Exception as e:
            log.warning("WGC 初始化失败: %s", e)

    # ------------------------------------------------------------------
    # PrintWindow（不受 WDA_EXCLUDEFROMCAPTURE 限制）
    # ------------------------------------------------------------------

    def _print_window_capture(self) -> np.ndarray | None:
        try:
            cr = win32gui.GetClientRect(self.hwnd)
            cw, ch = cr[2], cr[3]
            if cw == 0 or ch == 0:
                return None
            hDC    = win32gui.GetDC(self.hwnd)
            mfcDC  = win32ui.CreateDCFromHandle(hDC)
            memDC  = mfcDC.CreateCompatibleDC()
            bmp    = win32ui.CreateBitmap()
            bmp.CreateCompatibleBitmap(mfcDC, cw, ch)
            memDC.SelectObject(bmp)
            ctypes.windll.user32.PrintWindow(self.hwnd, memDC.GetSafeHdc(), _PW_RENDERFULLCONTENT)
            raw  = bmp.GetBitmapBits(True)
            bgr  = np.frombuffer(raw, dtype=np.uint8).reshape((ch, cw, 4))[:, :, :3].copy()
            win32gui.DeleteObject(bmp.GetHandle())
            memDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(self.hwnd, hDC)
            if bgr.mean() < 5:
                return None
            return bgr
        except Exception as e:
            log.debug("PrintWindow 失败: %s", e)
            return None

    # ------------------------------------------------------------------
    # mss 兜底
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
