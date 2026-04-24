# src/tray.py
import threading
import pystray
import keyboard
from PIL import Image, ImageDraw
import config
from src.main import FishingBot


def _make_icon(color: str) -> Image.Image:
    """创建 32×32 圆形托盘图标。"""
    img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((4, 4, 28, 28), fill=color)
    return img


def run_tray():
    bot = FishingBot()
    icon_ref: list[pystray.Icon] = []  # 用列表传递引用，避免闭包捕获问题

    def on_toggle(icon=None, item=None):
        bot.toggle()
        if icon_ref:
            icon_ref[0].icon = _make_icon('green' if bot.is_running else 'gray')
            icon_ref[0].title = f"NTE Fishing Bot — {bot.status}"

    def on_quit(icon, item):
        bot.stop()
        icon.stop()

    icon = pystray.Icon(
        name="NTE Fishing Bot",
        icon=_make_icon('gray'),
        title="NTE Fishing Bot — 已停止",
        menu=pystray.Menu(
            pystray.MenuItem("开始/暂停", on_toggle, default=True),
            pystray.MenuItem("退出", on_quit),
        )
    )
    icon_ref.append(icon)

    keyboard.add_hotkey(config.TOGGLE_HOTKEY, lambda: on_toggle())

    icon.run()
