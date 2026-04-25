"""
debug_run.py — 只读诊断脚本，不按任何键。
每帧打印检测数据，帮助校准阈值和确认检测逻辑。
用法：uv run python debug_run.py
"""
import sys
import time
import cv2
import numpy as np
import config
from src.capture import WindowCapture
from src.detector import StateDetector, GameState

# 强制 stdout UTF-8（Windows GBK 终端可能报编码错误）
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def p(*args, **kwargs):
    """print + 立即 flush，确保后台运行时输出不积压。"""
    print(*args, **kwargs, flush=True)

cap = WindowCapture(config.GAME_WINDOW_TITLE)
det = StateDetector()

# ── 窗口检测 ──────────────────────────────────────────────
if not cap.is_window_found():
    p(f"[ERROR] 找不到包含 '{config.GAME_WINDOW_TITLE}' 的窗口")
    p("  当前所有可见窗口：")
    import win32gui
    def _enum(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            t = win32gui.GetWindowText(hwnd)
            if t:
                try:
                    p(f"    [{hwnd}] {repr(t)}")
                except Exception:
                    pass
    win32gui.EnumWindows(_enum, None)
    exit(1)

w, h = cap.get_window_size()
p(f"[OK] 找到游戏窗口  hwnd={cap.hwnd}  尺寸={w}x{h}")
p(f"     BitBlt 截图区域配置:")
p(f"       钓鱼条 y=[{int(h*config.BAR_Y_START_RATIO)},{int(h*config.BAR_Y_END_RATIO)}]"
      f"  x=[{int(w*config.BAR_X_START_RATIO)},{int(w*config.BAR_X_END_RATIO)}]")
p(f"       钩子图标 y=[{int(h*config.HOOK_Y_START_RATIO)},{int(h*config.HOOK_Y_END_RATIO)}]"
      f"  x=[{int(w*config.HOOK_X_START_RATIO)},{int(w*config.HOOK_X_END_RATIO)}]")
p(f"     阈值: BITE_V>{config.BITE_V_THRESHOLD}  SLIDER_PX>{config.SLIDER_PX_THRESHOLD}")
p("=" * 72)
p(f"{'帧':>5}  {'状态':<8}  {'钩亮度':>7}  {'滑块px':>7}  {'详细'}")
p("-" * 72)

frame_n = 0
save_interval = 5.0   # 每隔 N 秒保存一张截图
last_save = time.time() - save_interval

try:
    while True:
        t0 = time.time()
        frame = cap.get_frame()
        if frame is None:
            p("[WARN] get_frame() 返回 None，检查窗口是否最小化")
            time.sleep(1.0)
            continue

        frame_n += 1
        fh, fw = frame.shape[:2]

        # ── 上钩检测原始值 ────────────────────────────────
        icon_crop = frame[
            int(fh * config.HOOK_Y_START_RATIO):int(fh * config.HOOK_Y_END_RATIO),
            int(fw * config.HOOK_X_START_RATIO):int(fw * config.HOOK_X_END_RATIO)
        ]
        icon_hsv = cv2.cvtColor(icon_crop, cv2.COLOR_BGR2HSV)
        avg_v = float(icon_hsv[:, :, 2].mean())

        # ── 滑块像素数 ────────────────────────────────────
        bar_crop = frame[
            int(fh * config.BAR_Y_START_RATIO):int(fh * config.BAR_Y_END_RATIO),
            int(fw * config.BAR_X_START_RATIO):int(fw * config.BAR_X_END_RATIO)
        ]
        bar_hsv = cv2.cvtColor(bar_crop, cv2.COLOR_BGR2HSV)
        slider_px = int(det._slider_mask(bar_hsv).sum())

        # ── 状态判断 ──────────────────────────────────────
        state = det.detect_state(frame)

        # ── 详细信息 ──────────────────────────────────────
        detail = ""
        if state == GameState.FISHING:
            fl, fr, px = det.detect_fishing_positions(frame)
            if fl is not None and fr is not None and px is not None:
                error = px - (fl + fr) / 2
                detail = f"鱼区=[{fl:4d},{fr:4d}]  竖线={px:4d}  误差={error:+5.0f}px"
            else:
                detail = f"位置检测失败  fl={fl} fr={fr} px={px}"

        bite_flag = "<<上钩!>>" if avg_v > config.BITE_V_THRESHOLD else ""
        bar_flag  = "<<钓鱼条>>" if slider_px > config.SLIDER_PX_THRESHOLD else ""

        p(f"{frame_n:5d}  {state.name:<8}  {avg_v:7.1f}  {slider_px:7d}  "
              f"{detail}  {bite_flag}{bar_flag}")

        # ── 定时保存截图 ──────────────────────────────────
        now = time.time()
        if now - last_save >= save_interval:
            fname = f"debug_frame_{frame_n:05d}.png"
            cv2.imwrite(fname, frame)
            p(f"  → 已保存截图: {fname}")
            last_save = now

        elapsed = time.time() - t0
        sleep_t = max(0, config.LOOP_INTERVAL - elapsed)
        time.sleep(sleep_t)

except KeyboardInterrupt:
    p("\n[停止] Ctrl+C 退出")
