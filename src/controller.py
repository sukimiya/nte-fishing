# src/controller.py
import logging
import time
import win32api
import win32con
import win32gui
import win32process
import keyboard
import config

log = logging.getLogger(__name__)

VK_MAP = {
    'f':      0x46,
    'a':      0x41,
    'd':      0x44,
    'escape': 0x1B,
}


def _make_lparam(vk: int, key_up: bool = False, repeat: bool = False) -> int:
    scan = win32api.MapVirtualKey(vk, 0)
    lParam = (scan << 16) | 1
    if repeat:
        lParam |= (1 << 30)
    if key_up:
        lParam |= (0xC0 << 24)
    return lParam


def _force_foreground(hwnd: int):
    try:
        fg_hwnd = win32gui.GetForegroundWindow()
        if fg_hwnd == hwnd:
            return
        fg_tid = win32process.GetWindowThreadProcessId(fg_hwnd)[0]
        tgt_tid = win32process.GetWindowThreadProcessId(hwnd)[0]
        win32api.AttachThreadInput(fg_tid, tgt_tid, True)
        win32gui.SetForegroundWindow(hwnd)
        win32api.AttachThreadInput(fg_tid, tgt_tid, False)
    except Exception as e:
        log.debug("force_foreground 失败: %s", e)


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
        """松开所有方向键。"""
        self._set_held(None)

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------

    def _set_held(self, key: str | None):
        if key == self._held:
            if key is not None:
                self._keydown(key, repeat=True)
            return
        if self._held is not None:
            self._keyup(self._held)
        if key is not None:
            self._keydown(key, repeat=False)
        self._held = key

    def _keydown(self, key: str, repeat: bool = False):
        """keyboard.press — 更新全局 GetAsyncKeyState，游戏通过轮询读取移动键状态。"""
        try:
            keyboard.press(key)
        except Exception as e:
            log.debug("keyboard.press 失败: %s", e)

    def _keyup(self, key: str):
        """keyboard.release — 释放移动键。"""
        try:
            keyboard.release(key)
        except Exception as e:
            log.debug("keyboard.release 失败: %s", e)

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
            log.warning("PostMessage _tap 失败 (%s)，改用 keyboard.send", e)
            _force_foreground(self.hwnd)
            keyboard.send(key)
