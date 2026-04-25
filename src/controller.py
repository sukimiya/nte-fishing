# src/controller.py
import logging
import time
import win32api
import win32con
import config
from src.input_inject import key_press, key_release

log = logging.getLogger(__name__)

VK_MAP = {
    'f':      0x46,
    'a':      0x41,
    'd':      0x44,
    'escape': 0x1B,
}


def _make_lparam(vk: int, key_up: bool = False) -> int:
    scan = win32api.MapVirtualKey(vk, 0)
    lParam = (scan << 16) | 1
    if key_up:
        lParam |= (0xC0 << 24)
    return lParam


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
        """短按一次：PostMessage KEYDOWN + sleep + KEYUP（F/ESC 走消息队列，后台可用）。"""
        vk = VK_MAP[key]
        lp_down = _make_lparam(vk, key_up=False)
        lp_up   = _make_lparam(vk, key_up=True)
        try:
            win32api.PostMessage(self.hwnd, win32con.WM_KEYDOWN, vk, lp_down)
            time.sleep(duration)
            win32api.PostMessage(self.hwnd, win32con.WM_KEYUP, vk, lp_up)
        except Exception as e:
            log.debug("PostMessage _tap 失败: %s", e)
