# src/main.py
import logging
import threading
import time
import config
from src.capture import WindowCapture
from src.detector import StateDetector, GameState
from src.controller import FishingController

log = logging.getLogger(__name__)


class FishingBot:

    def __init__(self):
        self.capturer = WindowCapture(config.GAME_WINDOW_TITLE)
        self.detector = StateDetector()
        self.controller: FishingController | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._state_log: str = "已停止"

    def start(self):
        if self._stop_event.is_set() or (self._thread is not None and self._thread.is_alive()):
            return
        self._stop_event.clear()
        self._state_log = "运行中"
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log.info("Bot 已启动")

    def stop(self):
        self._stop_event.set()
        log.info("Bot 停止信号已发送")

    def toggle(self):
        if self.is_running:
            self.stop()
        else:
            self.start()

    @property
    def is_running(self) -> bool:
        return not self._stop_event.is_set() and (
            self._thread is not None and self._thread.is_alive()
        )

    @property
    def status(self) -> str:
        return self._state_log

    def _loop(self):
        """主循环：状态机，约 30fps 运行。"""
        cast_at: float | None = None
        fishing_started = False
        prev_state: GameState | None = None

        while not self._stop_event.is_set():
            frame = self.capturer.get_frame()
            if frame is None:
                self._state_log = "找不到游戏窗口"
                log.warning("截图失败，找不到窗口 '%s'，1s 后重试", config.GAME_WINDOW_TITLE)
                time.sleep(1.0)
                continue

            if self.controller is None:
                w, h = self.capturer.get_window_size()
                log.info("绑定游戏窗口 hwnd=%d  尺寸=%dx%d", self.capturer.hwnd, w, h)
                self.controller = FishingController(self.capturer.hwnd)

            state = self.detector.detect_state(frame)

            if state != prev_state:
                log.info("状态切换: %s → %s", prev_state.name if prev_state else "None", state.name)
                if state == GameState.FISHING:
                    self.controller.enable_background_mode()
                elif prev_state == GameState.FISHING:
                    self.controller.disable_background_mode()
                prev_state = state

            if state == GameState.FISHING:
                fishing_started = True
                self._state_log = "钓鱼中"
                fl, fr, px = self.detector.detect_fishing_positions(frame)
                if fl is not None and fr is not None and px is not None:
                    error = px - (fl + fr) / 2
                    log.debug("FISHING  鱼区[%d,%d] 竖线=%d 误差=%+.0f", fl, fr, px, error)
                    self.controller.hold_direction(error)
                else:
                    log.debug("FISHING  位置检测失败 fl=%s fr=%s px=%s", fl, fr, px)
                    self.controller.release_all()

            elif state == GameState.BITE:
                self.controller.release_all()
                self._state_log = "上钩！按F"
                log.info("检测到上钩 → 按 F")
                self.controller.press_cast()
                time.sleep(0.3)

            else:  # IDLE
                self.controller.release_all()
                if fishing_started:
                    fishing_started = False
                    cast_at = None
                    self._state_log = "等待结果界面"
                    log.info("钓鱼结束，等待结果界面 %.1fs", config.END_WAIT_SEC)
                    time.sleep(config.END_WAIT_SEC)
                    self._state_log = "关闭结果界面"
                    log.info("点击空白处关闭结果界面")
                    self.controller.click_dismiss()
                    time.sleep(config.RESULT_WAIT_SEC)
                    continue

                now = time.time()
                need_cast = (
                    cast_at is None or
                    (now - cast_at) > config.MAX_WAIT_SEC
                )
                if need_cast:
                    self._state_log = "抛竿中"
                    log.info("IDLE → 抛竿（按 F）")
                    self.controller.press_cast()
                    cast_at = now
                    time.sleep(config.CAST_WAIT_SEC)
                else:
                    wait_s = now - cast_at
                    self._state_log = f"等待上钩 ({wait_s:.0f}s)"
                    log.debug("IDLE 等待上钩 %.0fs / %.0fs", wait_s, config.MAX_WAIT_SEC)

            time.sleep(config.LOOP_INTERVAL)

        if self.controller is not None:
            self.controller.release_all()
            self.controller.disable_background_mode()
        self._state_log = "已停止"
        log.info("Bot 主循环已退出")
