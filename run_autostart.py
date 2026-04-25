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

import config
from src.main import FishingBot

bot = FishingBot()
print("[启动] Bot 直接开始运行（无需 F12）", flush=True)
print(f"[提示] Bot 会自动将游戏拉到前台发送按键", flush=True)
print("[提示] Ctrl+C 退出", flush=True)
print("=" * 60, flush=True)

delay = config.STARTUP_DELAY_SEC
for i in range(delay, 0, -1):
    print(f"  {i}秒后开始...", flush=True)
    time.sleep(1)
print("  开始！", flush=True)

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
