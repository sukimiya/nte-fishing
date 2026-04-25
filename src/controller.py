# src/controller.py
import logging
import time
import win32api
import win32con
import vgamepad as vg
import config

log = logging.getLogger(__name__)

VK_MAP = {
    'f':      0x46,
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
        self._pad = vg.VX360Gamepad()
        self._stick_x = 0.0

    def press_cast(self):
        """按 F 键（抛竿或确认上钩）。"""
        self._tap('f', 0.05)

    def click_dismiss(self):
        """按 ESC 键关闭钓鱼结算界面。"""
        self._tap('escape', 0.05)

    def hold_direction(self, error: float):
        """左摇杆控制方向：error>0 → 向左（-1.0），error<0 → 向右（+1.0），死区内归零。"""
        if error > config.DEAD_ZONE:
            self._set_stick(-1.0)
        elif error < -config.DEAD_ZONE:
            self._set_stick(1.0)
        else:
            self._set_stick(0.0)

    def release_all(self):
        self._set_stick(0.0)

    # ------------------------------------------------------------------

    def _set_stick(self, x: float):
        if x == self._stick_x:
            return
        self._stick_x = x
        self._pad.left_joystick_float(x_value_float=x, y_value_float=0.0)
        self._pad.update()

    def _tap(self, key: str, duration: float):
        """短按一次：PostMessage KEYDOWN + sleep + KEYUP。"""
        vk = VK_MAP[key]
        lp_down = _make_lparam(vk, key_up=False)
        lp_up   = _make_lparam(vk, key_up=True)
        try:
            win32api.PostMessage(self.hwnd, win32con.WM_KEYDOWN, vk, lp_down)
            time.sleep(duration)
            win32api.PostMessage(self.hwnd, win32con.WM_KEYUP, vk, lp_up)
        except Exception as e:
            log.debug("PostMessage _tap 失败: %s", e)
