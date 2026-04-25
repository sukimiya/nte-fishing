# src/controller.py
import logging
import time
import win32api
import win32con
import keyboard
import config

log = logging.getLogger(__name__)

VK_MAP = {
    'f': 0x46,
    'a': 0x41,
    'd': 0x44,
}

# PostMessage 是否可用（首次失败后切换为 keyboard 方案）
_postmessage_ok = True


def _make_lparam(vk: int, key_up: bool = False) -> int:
    """构造 WM_KEYDOWN/WM_KEYUP 的 lParam。"""
    scan = win32api.MapVirtualKey(vk, 0)
    lParam = (scan << 16) | 1
    if key_up:
        lParam |= (0xC0 << 24)
    return lParam


class FishingController:

    def __init__(self, hwnd: int):
        self.hwnd = hwnd

    def press_cast(self):
        """按 F 键（抛竿或确认上钩）。"""
        self._press_key('f', 0.05)

    def adjust_line(self, error: float):
        """
        根据误差调整玩家竖线。
        error > 0: 偏右 → 按 A；error < 0: 偏左 → 按 D；|error| <= DEAD_ZONE: 不动。
        """
        if abs(error) <= config.DEAD_ZONE:
            return
        direction = 'a' if error > 0 else 'd'
        raw_ms = abs(error) * config.KEY_SCALE
        duration = max(config.KEY_MIN_DURATION,
                       min(raw_ms / 1000.0, config.KEY_MAX_DURATION))
        self._press_key(direction, duration)

    def _press_key(self, key: str, duration: float):
        """
        按键注入：优先使用 PostMessage（无需前台）；
        若被拒绝（UIPI/权限），自动切换为 keyboard.send（需游戏在前台）。
        """
        global _postmessage_ok
        if _postmessage_ok:
            try:
                vk = VK_MAP[key]
                lp_down = _make_lparam(vk, key_up=False)
                lp_up = _make_lparam(vk, key_up=True)
                win32api.PostMessage(self.hwnd, win32con.WM_KEYDOWN, vk, lp_down)
                time.sleep(duration)
                win32api.PostMessage(self.hwnd, win32con.WM_KEYUP, vk, lp_up)
                return
            except Exception as e:
                log.warning("PostMessage 失败 (%s)，切换为 keyboard 方案", e)
                _postmessage_ok = False

        # keyboard 方案：SendInput 级别，需游戏有焦点或在前台
        log.debug("keyboard.send '%s' %.3fs", key, duration)
        keyboard.press(key)
        time.sleep(duration)
        keyboard.release(key)
