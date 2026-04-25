"""
SendInput 标记注入 + WH_KEYBOARD_LL 拦截。

SendInput 在系统内核更新全局 GetAsyncKeyState（游戏通过轮询读取移动键），
然后异步通知 WH_KEYBOARD_LL 钩子；钩子发现 dwExtraInfo == OUR_MARKER，
返回非零值阻止 WM_KEYDOWN 派发到任何窗口，前台输入完全不受影响。
"""
import ctypes
import ctypes.wintypes
import threading
import logging
import win32api

log = logging.getLogger(__name__)

OUR_MARKER: int = 0xDEAD_CA7E

# ── KBDLLHOOKSTRUCT ──────────────────────────────────────────────────────────

class _KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode",      ctypes.c_uint32),
        ("scanCode",    ctypes.c_uint32),
        ("flags",       ctypes.c_uint32),
        ("time",        ctypes.c_uint32),
        ("dwExtraInfo", ctypes.c_size_t),
    ]

# 64 位 Windows：lParam 是 LPARAM = LONG_PTR = 8 字节，必须用 c_ssize_t 否则 OverflowError
_HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_uint, ctypes.c_ssize_t)

_CallNextHookEx = ctypes.windll.user32.CallNextHookEx
_CallNextHookEx.restype  = ctypes.c_long
_CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_ssize_t]

@_HOOKPROC
def _ll_hook(nCode: int, wParam: int, lParam: int) -> int:
    if nCode >= 0 and lParam:
        kb = ctypes.cast(lParam, ctypes.POINTER(_KBDLLHOOKSTRUCT)).contents
        if kb.dwExtraInfo == OUR_MARKER:
            # GetAsyncKeyState 已在 SendInput 处理时更新；此处只阻止 WM_KEYDOWN 派发
            return 1
    return _CallNextHookEx(None, nCode, wParam, lParam)


def _hook_thread_main() -> None:
    WH_KEYBOARD_LL = 13
    handle = ctypes.windll.user32.SetWindowsHookExW(WH_KEYBOARD_LL, _ll_hook, None, 0)
    if not handle:
        log.warning("WH_KEYBOARD_LL 安装失败 (err=%d)", ctypes.windll.kernel32.GetLastError())
        return
    log.debug("WH_KEYBOARD_LL 钩子已安装")
    msg = ctypes.wintypes.MSG()
    while ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
        ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
    ctypes.windll.user32.UnhookWindowsHookEx(handle)
    log.debug("WH_KEYBOARD_LL 钩子已卸载")


threading.Thread(target=_hook_thread_main, daemon=True, name="kbd-ll-hook").start()

# ── SendInput ────────────────────────────────────────────────────────────────

class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk",         ctypes.c_uint16),
        ("wScan",       ctypes.c_uint16),
        ("dwFlags",     ctypes.c_uint32),
        ("time",        ctypes.c_uint32),
        ("dwExtraInfo", ctypes.c_size_t),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("_pad", ctypes.c_byte * 32)]

class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_uint32), ("_u", _INPUT_UNION)]

_KEYEVENTF_KEYUP = 0x0002


def key_press(vk: int) -> None:
    inp = _INPUT()
    inp.type = 1  # INPUT_KEYBOARD
    inp._u.ki.wVk = vk
    inp._u.ki.wScan = win32api.MapVirtualKey(vk, 0)
    inp._u.ki.dwFlags = 0
    inp._u.ki.dwExtraInfo = OUR_MARKER
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def key_release(vk: int) -> None:
    inp = _INPUT()
    inp.type = 1
    inp._u.ki.wVk = vk
    inp._u.ki.wScan = win32api.MapVirtualKey(vk, 0)
    inp._u.ki.dwFlags = _KEYEVENTF_KEYUP
    inp._u.ki.dwExtraInfo = OUR_MARKER
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
