# src/tray.py
import ctypes
import threading
import time
import pystray
from PIL import Image, ImageDraw
import config
from src.main import FishingBot

_VK_F12 = 0x7B


def _make_icon(color: str) -> Image.Image:
    """创建 32×32 圆形托盘图标。"""
    img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((4, 4, 28, 28), fill=color)
    return img


def _start_f12_poll(on_toggle):
    """后台线程轮询 F12，替代 keyboard 库的全局热键（避免 hook 冲突）。"""
    def _poll():
        prev = False
        while True:
            now = bool(ctypes.windll.user32.GetAsyncKeyState(_VK_F12) & 0x8000)
            if now and not prev:
                on_toggle()
            prev = now
            time.sleep(0.1)
    t = threading.Thread(target=_poll, daemon=True)
    t.start()


def run_tray():
    bot = FishingBot()
    icon_ref: list[pystray.Icon] = []

    def on_toggle():
        bot.toggle()
        if icon_ref:
            icon_ref[0].icon = _make_icon('green' if bot.is_running else 'gray')
            icon_ref[0].title = f"NTE Fishing Bot — {bot.status}"

    def on_toggle_menu(icon, item):
        on_toggle()

    def on_quit(icon, item):
        bot.stop()
        icon.stop()

    icon = pystray.Icon(
        name="NTE Fishing Bot",
        icon=_make_icon('gray'),
        title="NTE Fishing Bot — 已停止",
        menu=pystray.Menu(
            pystray.MenuItem("开始/暂停", on_toggle_menu, default=True),
            pystray.MenuItem("退出", on_quit),
        )
    )
    icon_ref.append(icon)

    _start_f12_poll(on_toggle)
    icon.run()
