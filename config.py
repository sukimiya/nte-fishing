GAME_WINDOW_TITLE = "异环"
TOGGLE_HOTKEY = "f12"
LOOP_INTERVAL = 0.033        # 主循环间隔（秒），约 30fps

# 钓鱼条检测区域（相对于窗口尺寸的比例）
BAR_Y_START_RATIO = 0.052    # 75/1440
BAR_Y_END_RATIO   = 0.073    # 105/1440
BAR_X_START_RATIO = 0.15
BAR_X_END_RATIO   = 0.85

# 鱼的滑块颜色（HSV，OpenCV 0-179 range）
SLIDER_H_LOW  = 75
SLIDER_H_HIGH = 90
SLIDER_S_MIN  = 150
SLIDER_V_MIN  = 180
SLIDER_PX_THRESHOLD = 200    # 最少像素数才判定条形可见

# 玩家竖线颜色
MARKER_H_LOW  = 22
MARKER_H_HIGH = 40
MARKER_V_MIN  = 235
MARKER_MAX_WIDTH = 20        # 竖线宽度上限（像素）
MARKER_INNER_X_START = 350
MARKER_INNER_X_END   = 1263

# 钩子图标区域（相对比例）
HOOK_Y_START_RATIO = 0.82
HOOK_Y_END_RATIO   = 0.95
HOOK_X_START_RATIO = 0.89
HOOK_X_END_RATIO   = 0.97
BITE_V_THRESHOLD   = 190.0   # 平均亮度超过此值 → 上钩

# 按键控制参数
DEAD_ZONE        = 10        # 控制死区（像素误差）
KEY_SCALE        = 1.0       # 按键时长系数（ms/px）
KEY_MAX_DURATION = 0.15      # 单次最大按键时长（秒）
KEY_MIN_DURATION = 0.01      # 单次最小按键时长（秒）

# 状态机时序
CAST_WAIT_SEC    = 1.0       # 抛竿后等待时间（秒）
END_WAIT_SEC     = 1.5       # 钓鱼结束后等待时间（秒）
MAX_WAIT_SEC     = 60.0      # 等待上钩超时（秒），超时重新抛竿

# 启动倒计时（秒）：给用户切换到游戏窗口的时间
STARTUP_DELAY_SEC = 5
