"""
run_autostart.py — 直接启动主循环（不经托盘），方便测试。
Ctrl+C 退出。
"""
import logging
import sys
import time

logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    force=True,
)
# 屏蔽 PIL 插件噪音
logging.getLogger("PIL").setLevel(logging.WARNING)

from src.main import FishingBot

bot = FishingBot()
print("[启动] Bot 直接开始运行（无需 F12）", flush=True)
print("[提示] 请确保游戏窗口在前台（keyboard 按键需要焦点）", flush=True)
print("[提示] Ctrl+C 退出", flush=True)
print("=" * 60, flush=True)

bot.start()

try:
    while bot.is_running:
        print(f"  状态: {bot.status}", flush=True)
        time.sleep(2.0)
except KeyboardInterrupt:
    pass
finally:
    bot.stop()
    print("\n[停止] Bot 已退出", flush=True)
