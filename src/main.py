# src/main.py
import threading
import time
import config
from src.capture import WindowCapture
from src.detector import StateDetector, GameState
from src.controller import FishingController


class FishingBot:

    def __init__(self):
        self.capturer = WindowCapture(config.GAME_WINDOW_TITLE)
        self.detector = StateDetector()
        self.controller: FishingController | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._state_log: str = "已停止"

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def toggle(self):
        if self._running:
            self.stop()
        else:
            self.start()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def status(self) -> str:
        return self._state_log

    def _loop(self):
        """主循环：状态机，约 30fps 运行。"""
        cast_at: float | None = None
        fishing_started = False

        while self._running:
            frame = self.capturer.get_frame()
            if frame is None:
                self._state_log = "找不到游戏窗口"
                time.sleep(1.0)
                continue

            if self.controller is None:
                self.controller = FishingController(self.capturer.hwnd)

            state = self.detector.detect_state(frame)

            if state == GameState.FISHING:
                fishing_started = True
                self._state_log = "钓鱼中"
                fl, fr, px = self.detector.detect_fishing_positions(frame)
                if fl is not None and fr is not None and px is not None:
                    error = px - (fl + fr) / 2
                    self.controller.adjust_line(error)

            elif state == GameState.BITE:
                self._state_log = "上钩！按F"
                self.controller.press_cast()
                time.sleep(0.3)

            else:  # IDLE
                if fishing_started:
                    self._state_log = "钓鱼结束，等待中"
                    fishing_started = False
                    cast_at = None
                    time.sleep(config.END_WAIT_SEC)
                    continue

                now = time.time()
                need_cast = (
                    cast_at is None or
                    (now - cast_at) > config.MAX_WAIT_SEC
                )
                if need_cast:
                    self._state_log = "抛竿中"
                    self.controller.press_cast()
                    cast_at = now
                    time.sleep(config.CAST_WAIT_SEC)
                else:
                    self._state_log = f"等待上钩 ({now - cast_at:.0f}s)"

            time.sleep(config.LOOP_INTERVAL)

        self._state_log = "已停止"
