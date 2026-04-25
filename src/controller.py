# src/controller.py
import logging
import time
import config
from src.input_inject import key_press, key_release

log = logging.getLogger(__name__)

VK_MAP = {
    'f':      0x46,
    'a':      0x41,
    'd':      0x44,
    'escape': 0x1B,
}


class FishingController:

    def __init__(self, hwnd: int):
        self.hwnd = hwnd
        self._held: str | None = None

    def press_cast(self):
        """按 F 键（抛竿或确认上钩）。"""
        self._tap('f', 0.05)

    def click_dismiss(self):
        """按 ESC 键关闭钓鱼结算界面。"""
        self._tap('escape', 0.05)

    def hold_direction(self, error: float):
        """持续按住方向键：error>0 → A（向左），error<0 → D（向右），死区内松开。"""
        if error > config.DEAD_ZONE:
            self._set_held('a')
        elif error < -config.DEAD_ZONE:
            self._set_held('d')
        else:
            self._set_held(None)

    def release_all(self):
        self._set_held(None)

    # ------------------------------------------------------------------

    def _set_held(self, key: str | None):
        if key == self._held:
            return
        if self._held is not None:
            key_release(VK_MAP[self._held])
        if key is not None:
            key_press(VK_MAP[key])
        self._held = key

    def _tap(self, key: str, duration: float):
        """短按：SendInput 路径，后台也能触发 GetAsyncKeyState，游戏可见。"""
        vk = VK_MAP[key]
        key_press(vk)
        time.sleep(duration)
        key_release(vk)
