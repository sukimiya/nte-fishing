# 异环（NTE）钓鱼辅助工具 — 设计规格

## 背景

为游戏"异环（NTE）"开发全自动钓鱼辅助工具。目标：游戏在后台运行时，工具自动完成完整钓鱼流程（抛竿 → 检测上钩 → 钓鱼小游戏），玩家挂机无需干预。

**技术选型：**
- 语言：Python
- 截图：Win32 BitBlt（无需游戏在前台）
- 按键：PostMessage WM_KEYDOWN/WM_KEYUP（无需焦点）
- 控制界面：系统托盘图标 + F12 热键

---

## 项目结构

```
nte-fishing/
├── main.py          # 入口：系统托盘 + 主循环
├── capture.py       # 窗口截图模块
├── detector.py      # 状态检测模块
├── controller.py    # 按键注入模块
├── config.py        # 用户配置项
└── requirements.txt
```

---

## 状态机

```
IDLE
  └─ 检测到待机状态 → 按 F → WAITING_BITE
        └─ 检测到上钩（发光+蓝圈） → 按 F → FISHING
              └─ 钓鱼小游戏：持续控制 A/D
                    ├─ 鱼耐力→0 → SUCCESS → IDLE（继续下一轮）
                    └─ 鱼线→0   → FAIL    → IDLE（继续下一轮）
```

主循环频率：**30fps（约33ms/帧）**，在独立线程中运行。

---

## 模块详细设计

### capture.py — 窗口截图

**职责：** 根据窗口标题找到游戏 HWND，用 BitBlt 从游戏 DC 截取指定区域，返回 numpy 数组。

- 游戏窗口可见但不需要在前台（支持后台截图）
- 支持全屏模式（自动检测：窗口尺寸等于屏幕分辨率时，改用 mss 截全屏坐标）
- 截图区域以窗口宽高的**比例**表示，适配不同分辨率

**接口：**
```python
class WindowCapture:
    def __init__(self, window_title: str)
    def get_frame(self, region: tuple = None) -> np.ndarray  # region: (x%, y%, w%, h%)
    def is_window_found(self) -> bool
```

---

### detector.py — 状态检测

**职责：** 分析截图帧，返回当前游戏状态及钓鱼小游戏的位置数据。

**截图区域划分：**

| 区域 | 比例位置 | 用途 |
|------|---------|------|
| 右下角区域 | x:75%-100%, y:75%-100% | 检测鱼钩图标（IDLE / WAITING_BITE） |
| 顶部中央区域 | x:20%-80%, y:0%-15% | 检测钓鱼状态条（FISHING） |

**各状态检测方法：**

| 状态 | 检测逻辑 |
|------|---------|
| IDLE | 右下角区域内蓝色像素占比 < 阈值，亮度正常 |
| WAITING_BITE | 右下角区域内 HSV(100-130°) 蓝色像素占比 > 阈值，且亮度突然升高 |
| FISHING | 顶部中央区域内 HSV 绿色像素连续水平分布，宽度 > 最小长度阈值 |

**钓鱼小游戏位置检测：**
```python
# 绿色滑块（鱼区域）：找绿色像素在 X 轴的左边界和右边界
fish_left, fish_right = detect_green_slider(frame)

# 玩家竖线：找黄色/白色细竖线的 X 坐标中心
player_x = detect_player_line(frame)
```

**接口：**
```python
class StateDetector:
    def detect_state(self, frame: np.ndarray) -> GameState  # IDLE/WAITING_BITE/FISHING
    def detect_fishing_positions(self, frame: np.ndarray) -> tuple  # (fish_left, fish_right, player_x)
```

---

### controller.py — 按键注入

**职责：** 通过 PostMessage 向游戏窗口发送按键，无需游戏在前台。

**按键实现：**
```python
def press_key(hwnd, key: str, duration: float):
    vk = VK_MAP[key]  # F, A, D 的虚拟键码
    win32api.PostMessage(hwnd, WM_KEYDOWN, vk, make_lparam(vk))
    time.sleep(duration)
    win32api.PostMessage(hwnd, WM_KEYUP, vk, make_lparam(vk, up=True))
```

**钓鱼控制逻辑（比例控制）：**
```python
fish_center = (fish_left + fish_right) / 2
error = player_x - fish_center  # 正值=偏右，负值=偏左

if abs(error) > DEAD_ZONE:
    direction = 'a' if error > 0 else 'd'
    duration = clamp(abs(error) * KEY_SCALE / 1000, 0.01, KEY_MAX_DURATION)
    press_key(hwnd, direction, duration)
```

**接口：**
```python
class FishingController:
    def press_cast(self)            # 按 F 抛竿/上钩确认
    def adjust_line(self, error: float)   # 根据误差控制 A/D
```

---

### main.py — 系统托盘 + 主循环

**职责：** 程序入口，管理系统托盘图标、热键监听、主循环线程。

- 使用 `pystray` 创建系统托盘图标
  - 绿色图标：自动化运行中
  - 灰色图标：已暂停
- 右键菜单：开始/暂停、退出
- 热键 `F12`（可配置）：快速开关
- 主循环在 `threading.Thread` 中运行，不阻塞托盘

**主循环逻辑：**
```python
while running:
    frame = capturer.get_frame()
    state = detector.detect_state(frame)

    if state == IDLE:
        controller.press_cast()           # 抛竿
        current_state = WAITING_BITE

    elif state == WAITING_BITE:
        controller.press_cast()           # 确认上钩
        current_state = FISHING

    elif state == FISHING:
        fish_l, fish_r, player = detector.detect_fishing_positions(frame)
        controller.adjust_line(player - (fish_l + fish_r) / 2)

    time.sleep(LOOP_INTERVAL)
```

---

### config.py — 用户配置

```python
GAME_WINDOW_TITLE = "异环"
TOGGLE_HOTKEY = "f12"
LOOP_INTERVAL = 0.033        # 主循环间隔（秒）
DEAD_ZONE = 5                # 控制死区（像素）
KEY_SCALE = 0.8              # 按键时长比例系数（ms/px）
KEY_MAX_DURATION = 0.15      # 单次最大按键时长（秒）

# HSV 颜色阈值（BGR转HSV后的范围，需根据实际画面校准）
BITE_BLUE_HSV_LOWER = (100, 100, 100)   # 上钩检测：蓝色下界
BITE_BLUE_HSV_UPPER = (130, 255, 255)   # 上钩检测：蓝色上界
BITE_PIXEL_THRESHOLD = 0.03             # 蓝色像素占比触发阈值

FISH_GREEN_HSV_LOWER = (40, 80, 80)     # 绿色滑块下界
FISH_GREEN_HSV_UPPER = (80, 255, 255)   # 绿色滑块上界
FISH_MIN_WIDTH = 20                     # 滑块最小宽度（像素），过滤噪声
```

---

## 依赖库

```
opencv-python>=4.8
pywin32>=306
pystray>=0.19
Pillow>=10.0
keyboard>=0.13
numpy>=1.24
```

---

## 风险点

| 风险 | 说明 | 应对 |
|------|------|------|
| PostMessage 无效 | 游戏若使用 DirectInput/RawInput 则不响应 PostMessage | 实测后可改用 SendInput（需前台）或 Interception 驱动 |
| 颜色阈值偏差 | 分辨率、画质、亮度设置影响 HSV 值 | config.py 提供可调阈值，首次运行时需校准 |
| 检测区域坐标 | 鱼钩图标和状态条位置依赖 UI 布局 | 用比例坐标而非固定像素，降低分辨率敏感性 |
| 上钩误检 | WAITING_BITE 检测可能误触发 | 加入亮度变化量判断（delta > 阈值），而非绝对亮度 |

---

## 验证步骤

1. 启动工具，系统托盘出现图标（灰色=待机）
2. 按 F12，图标变绿，进入运行状态
3. 进入游戏钓鱼场景，观察工具是否自动按 F 抛竿
4. 等待上钩，观察蓝色光晕检测是否触发自动按 F
5. 钓鱼小游戏中，观察 A/D 是否自动将玩家竖线保持在鱼滑块内
6. 捕获成功或失败后，观察是否自动回到 IDLE 继续下一轮
