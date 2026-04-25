"""运行 Bot 并输出完整日志，用于调试。"""
import logging
import sys

logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    force=True,
)

from src.tray import run_tray
run_tray()
