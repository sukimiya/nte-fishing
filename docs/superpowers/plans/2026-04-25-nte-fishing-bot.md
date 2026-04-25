# 异环钓鱼辅助工具 实现计划

> **面向 AI 代理的工作者：** 使用 superpowers:subagent-driven-development 或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法跟踪进度。

**目标：** 全自动钓鱼辅助工具，游戏在后台运行，自动完成抛竿→检测上钩→钓鱼小游戏全流程

**架构：** 使用 Win32 BitBlt 后台截图，PostMessage 按键注入，OpenCV 颜色检测识别状态和位置，pystray 系统托盘控制。

**技术栈：** Python, opencv-python, pywin32, pystray, keyboard, numpy

**已校准参数（基于 2304×1440 录像）：**
- 条形区域 y：`[75:105]`（相当于 5.2%~7.3% 高度）
- 条形区域 x：`[int(w*0.15):int(w*0.85)]`
- 鱼的滑块色：HSV H∈[75,90], S>150, V>180（青绿色）
- 玩家竖线色：HSV H∈[22,40], V>235（黄白亮线），宽度<20px，x 范围排除图标区 350-1263
- 上钩检测：钩子图标区域 y=[82%:95%], x=[89%:97%]，avg_V > 190
- 条形可见阈值：>200 个匹配像素

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `src/capture.py` | 通过 HWND BitBlt 截取游戏窗口区域（后台可用）|
| `src/detector.py` | 状态检测：IDLE/BITE/FISHING，以及钓鱼条位置计算 |
| `src/controller.py` | PostMessage 按键注入（F/A/D），比例控制逻辑 |
| `src/tray.py` | pystray 系统托盘图标 + F12 热键开关 |
| `src/main.py` | 状态机主循环，组装所有模块 |
| `config.py` | 所有可调参数集中管理 |
| `tests/test_detector.py` | 基于录像帧的检测器单元测试 |
| `tests/test_controller.py` | 控制逻辑单元测试（不依赖游戏） |

---

## 任务 1：项目初始化与配置

**文件：**
- 修改：`pyproject.toml`（uv 已创建）
- 创建：`config.py`
- 创建：`src/__init__.py`

- [ ] **步骤 1：创建 src 目录**

```bash
mkdir -p src tests
touch src/__init__.py tests/__init__.py
```

- [ ] **步骤 2：更新 pyproject.toml 确认依赖完整**

检查 `pyproject.toml` 中已有的依赖（uv 已安装）：
```
opencv-python, pywin32, pystray, Pillow, keyboard, numpy
```
若缺少任何一项：`uv add <包名>`

- [ ] **步骤 3：创建 config.py**

```python
# config.py
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
# 排除两侧图标的内部区域（相对于条形宽度）
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
```

- [ ] **步骤 4：Commit**

```bash
git init
git add pyproject.toml config.py src/ tests/
git commit -m "feat: project setup with config"
```

---

## 任务 2：窗口截图模块 capture.py

**文件：**
- 创建：`src/capture.py`
- 测试：`tests/test_capture.py`

- [ ] **步骤 1：编写失败测试**

```python
# tests/test_capture.py
import pytest
from unittest.mock import patch, MagicMock
import numpy as np

def test_window_not_found_returns_none():
    with patch('win32gui.FindWindow', return_value=0):
        from src.capture import WindowCapture
        cap = WindowCapture("不存在的窗口")
        assert cap.hwnd == 0
        assert not cap.is_window_found()

def test_get_frame_returns_none_when_no_window():
    with patch('win32gui.FindWindow', return_value=0):
        from src.capture import WindowCapture
        cap = WindowCapture("不存在的窗口")
        assert cap.get_frame() is None

def test_get_region_returns_correct_shape():
    """Given a mock HWND, get_frame with region returns ndarray of expected shape."""
    mock_hwnd = 12345
    mock_array = np.zeros((1440, 2304, 3), dtype=np.uint8)
    with patch('win32gui.FindWindow', return_value=mock_hwnd), \
         patch('win32gui.GetClientRect', return_value=(0,0,2304,1440)), \
         patch('src.capture.WindowCapture._bitblt_capture', return_value=mock_array):
        from src.capture import WindowCapture
        cap = WindowCapture("异环")
        frame = cap.get_frame(region=(0.0, 0.0, 1.0, 1.0))
        assert frame is not None
        assert frame.shape == (1440, 2304, 3)
```

- [ ] **步骤 2：运行测试确认失败**

```bash
uv run pytest tests/test_capture.py -v
```
预期：ImportError 或 ModuleNotFoundError（src/capture.py 不存在）

- [ ] **步骤 3：实现 capture.py**

```python
# src/capture.py
import numpy as np
import win32gui
import win32ui
import win32con
from PIL import Image


class WindowCapture:
    def __init__(self, window_title: str):
        self.window_title = window_title
        self.hwnd = win32gui.FindWindow(None, window_title)

    def is_window_found(self) -> bool:
        return self.hwnd != 0

    def refresh_hwnd(self):
        """重新查找窗口句柄（窗口重启后需要调用）"""
        self.hwnd = win32gui.FindWindow(None, self.window_title)

    def get_window_size(self) -> tuple[int, int]:
        """返回 (width, height)，找不到窗口返回 (0, 0)"""
        if not self.is_window_found():
            return (0, 0)
        rect = win32gui.GetClientRect(self.hwnd)
        return (rect[2], rect[3])

    def get_frame(self, region: tuple[float, float, float, float] | None = None) -> np.ndarray | None:
        """
        截取游戏窗口画面，无需游戏在前台。
        region: (x_start%, y_start%, x_end%, y_end%)，不传则截取整个窗口。
        返回 BGR numpy 数组，失败返回 None。
        """
        if not self.is_window_found():
            self.refresh_hwnd()
            if not self.is_window_found():
                return None

        full = self._bitblt_capture()
        if full is None:
            return None

        if region is None:
            return full

        h, w = full.shape[:2]
        x1 = int(region[0] * w)
        y1 = int(region[1] * h)
        x2 = int(region[2] * w)
        y2 = int(region[3] * h)
        return full[y1:y2, x1:x2]

    def _bitblt_capture(self) -> np.ndarray | None:
        """使用 BitBlt 从游戏 DC 截图，返回 BGR numpy 数组。"""
        try:
            rect = win32gui.GetClientRect(self.hwnd)
            w, h = rect[2], rect[3]
            if w == 0 or h == 0:
                return None

            hwnd_dc = win32gui.GetWindowDC(self.hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()

            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
            save_dc.SelectObject(bitmap)

            save_dc.BitBlt((0, 0), (w, h), mfc_dc, (0, 0), win32con.SRCCOPY)

            bmp_info = bitmap.GetInfo()
            bmp_str = bitmap.GetBitmapBits(True)
            img = Image.frombuffer(
                'RGB', (bmp_info['bmWidth'], bmp_info['bmHeight']),
                bmp_str, 'raw', 'BGRX', 0, 1
            )
            frame = np.array(img)
            frame = frame[:, :, :3]  # drop alpha if present
            # PIL RGB → OpenCV BGR
            frame = frame[:, :, ::-1].copy()

            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(self.hwnd, hwnd_dc)
            win32gui.DeleteObject(bitmap.GetHandle())

            return frame
        except Exception:
            return None
```

- [ ] **步骤 4：运行测试确认通过**

```bash
uv run pytest tests/test_capture.py -v
```
预期：3 tests PASSED

- [ ] **步骤 5：Commit**

```bash
git add src/capture.py tests/test_capture.py
git commit -m "feat: add WindowCapture module with BitBlt backend"
```

---

## 任务 3：状态检测模块 detector.py

**文件：**
- 创建：`src/detector.py`
- 测试：`tests/test_detector.py`

- [ ] **步骤 1：编写失败测试（使用真实录像帧）**

```python
# tests/test_detector.py
import cv2
import numpy as np
import pytest
from src.detector import StateDetector, GameState

FRAMES = {
    'idle':    'frames/bite_f2950.png',
    'bite':    'frames/bite_f3050.png',
    'fishing_3': 'frames/v1_f03_374.png',
    'fishing_4': 'frames/v1_f04_481.png',
    'fishing_5': 'frames/v1_f05_587.png',
    'fishing_6': 'frames/v1_f06_694.png',
}

@pytest.fixture
def detector():
    return StateDetector()

def test_detect_idle_state(detector):
    frame = cv2.imread(FRAMES['idle'])
    assert detector.detect_state(frame) == GameState.IDLE

def test_detect_bite_state(detector):
    frame = cv2.imread(FRAMES['bite'])
    assert detector.detect_state(frame) == GameState.BITE

@pytest.mark.parametrize("key", ['fishing_3', 'fishing_4', 'fishing_5', 'fishing_6'])
def test_detect_fishing_state(detector, key):
    frame = cv2.imread(FRAMES[key])
    assert detector.detect_state(frame) == GameState.FISHING

def test_detect_fishing_positions_in_range(detector):
    """fish_left < fish_right, player_x in [fish_left-200, fish_right+200]"""
    frame = cv2.imread(FRAMES['fishing_3'])
    fl, fr, px = detector.detect_fishing_positions(frame)
    assert fl is not None and fr is not None and px is not None
    assert fl < fr
    assert fl - 200 < px < fr + 200

@pytest.mark.parametrize("key,expected_error_sign", [
    ('fishing_3', +1),   # player to right of center (+119px)
    ('fishing_4',  0),   # player near center (+22px, within dead zone)
])
def test_fishing_error_sign(detector, key, expected_error_sign):
    frame = cv2.imread(FRAMES[key])
    fl, fr, px = detector.detect_fishing_positions(frame)
    fish_center = (fl + fr) / 2
    error = px - fish_center
    if expected_error_sign == +1:
        assert error > 10
    elif expected_error_sign == 0:
        assert abs(error) < 50  # near center
```

- [ ] **步骤 2：运行测试确认失败**

```bash
uv run pytest tests/test_detector.py -v
```
预期：ImportError（src/detector.py 不存在）

- [ ] **步骤 3：实现 detector.py**

```python
# src/detector.py
from enum import Enum, auto
import cv2
import numpy as np
import config


class GameState(Enum):
    IDLE = auto()
    BITE = auto()
    FISHING = auto()


class StateDetector:

    def detect_state(self, frame: np.ndarray) -> GameState:
        """
        检测当前游戏状态。
        优先级：FISHING > BITE > IDLE
        """
        if self._is_bar_visible(frame):
            return GameState.FISHING
        if self._is_bite(frame):
            return GameState.BITE
        return GameState.IDLE

    def detect_fishing_positions(self, frame: np.ndarray) -> tuple[int | None, int | None, int | None]:
        """
        返回 (fish_left, fish_right, player_x)，单位为像素（bar region 坐标系）。
        任一无法检测时对应值返回 None。
        """
        h, w = frame.shape[:2]
        bx1 = int(w * config.BAR_X_START_RATIO)
        bx2 = int(w * config.BAR_X_END_RATIO)
        by1 = int(h * config.BAR_Y_START_RATIO)
        by2 = int(h * config.BAR_Y_END_RATIO)

        bar = frame[by1:by2, bx1:bx2]
        hsv = cv2.cvtColor(bar, cv2.COLOR_BGR2HSV)

        fish_left, fish_right = self._find_slider(hsv)
        player_x = self._find_player_marker(hsv)

        return fish_left, fish_right, player_x

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _is_bar_visible(self, frame: np.ndarray) -> bool:
        h, w = frame.shape[:2]
        bar = frame[
            int(h * config.BAR_Y_START_RATIO):int(h * config.BAR_Y_END_RATIO),
            int(w * config.BAR_X_START_RATIO):int(w * config.BAR_X_END_RATIO)
        ]
        hsv = cv2.cvtColor(bar, cv2.COLOR_BGR2HSV)
        mask = (
            (hsv[:, :, 0] >= config.SLIDER_H_LOW) &
            (hsv[:, :, 0] <= config.SLIDER_H_HIGH) &
            (hsv[:, :, 1] > config.SLIDER_S_MIN) &
            (hsv[:, :, 2] > config.SLIDER_V_MIN)
        )
        return int(mask.sum()) > config.SLIDER_PX_THRESHOLD

    def _is_bite(self, frame: np.ndarray) -> bool:
        h, w = frame.shape[:2]
        icon = frame[
            int(h * config.HOOK_Y_START_RATIO):int(h * config.HOOK_Y_END_RATIO),
            int(w * config.HOOK_X_START_RATIO):int(w * config.HOOK_X_END_RATIO)
        ]
        hsv = cv2.cvtColor(icon, cv2.COLOR_BGR2HSV)
        avg_v = float(hsv[:, :, 2].mean())
        return avg_v > config.BITE_V_THRESHOLD

    def _find_slider(self, bar_hsv: np.ndarray) -> tuple[int | None, int | None]:
        mask = (
            (bar_hsv[:, :, 0] >= config.SLIDER_H_LOW) &
            (bar_hsv[:, :, 0] <= config.SLIDER_H_HIGH) &
            (bar_hsv[:, :, 1] > config.SLIDER_S_MIN) &
            (bar_hsv[:, :, 2] > config.SLIDER_V_MIN)
        )
        cols = np.where(mask.any(axis=0))[0]
        if len(cols) == 0:
            return None, None
        return int(cols[0]), int(cols[-1])

    def _find_player_marker(self, bar_hsv: np.ndarray) -> int | None:
        """
        在排除图标区域后查找玩家竖线（黄白色亮线，H=22-40, V>235）。
        返回竖线中心 x（bar region 坐标系），找不到返回 None。
        """
        inner = bar_hsv[
            :,
            config.MARKER_INNER_X_START:config.MARKER_INNER_X_END
        ]
        mask = (
            (inner[:, :, 0] >= config.MARKER_H_LOW) &
            (inner[:, :, 0] <= config.MARKER_H_HIGH) &
            (inner[:, :, 2] > config.MARKER_V_MIN)
        )
        cols = np.where(mask.any(axis=0))[0]
        if len(cols) == 0:
            return None

        # 聚类，取最窄的一簇
        groups: list[tuple[int, int]] = []
        s, p = int(cols[0]), int(cols[0])
        for c in cols[1:]:
            if c - p > 5:
                groups.append((s, p))
                s = int(c)
            p = int(c)
        groups.append((s, p))

        narrow = [(s, p) for s, p in groups if (p - s) < config.MARKER_MAX_WIDTH]
        if not narrow:
            return None

        best = min(narrow, key=lambda g: g[1] - g[0])
        return int(np.mean(best)) + config.MARKER_INNER_X_START
```

- [ ] **步骤 4：运行测试确认通过**

```bash
uv run pytest tests/test_detector.py -v
```
预期：7 tests PASSED

- [ ] **步骤 5：Commit**

```bash
git add src/detector.py tests/test_detector.py
git commit -m "feat: add StateDetector with bar/bite/fishing detection"
```

---

## 任务 4：按键注入模块 controller.py

**文件：**
- 创建：`src/controller.py`
- 测试：`tests/test_controller.py`

- [ ] **步骤 1：编写失败测试**

```python
# tests/test_controller.py
import pytest
from unittest.mock import patch, call
import sys

# Mock win32api before importing controller
sys.modules['win32api'] = __import__('unittest.mock', fromlist=['MagicMock']).MagicMock()
sys.modules['win32con'] = __import__('unittest.mock', fromlist=['MagicMock']).MagicMock()

from src.controller import FishingController

@pytest.fixture
def controller():
    return FishingController(hwnd=12345)

def test_adjust_line_large_positive_error_presses_a(controller):
    """error > DEAD_ZONE → press 'A' (move player left)"""
    with patch.object(controller, '_press_key') as mock_press:
        controller.adjust_line(error=+100)
        mock_press.assert_called_once()
        key, duration = mock_press.call_args[0]
        assert key == 'a'
        assert 0.01 <= duration <= 0.15

def test_adjust_line_large_negative_error_presses_d(controller):
    """error < -DEAD_ZONE → press 'D' (move player right)"""
    with patch.object(controller, '_press_key') as mock_press:
        controller.adjust_line(error=-80)
        mock_press.assert_called_once()
        key, duration = mock_press.call_args[0]
        assert key == 'd'
        assert 0.01 <= duration <= 0.15

def test_adjust_line_within_dead_zone_presses_nothing(controller):
    """error within dead zone → no key press"""
    with patch.object(controller, '_press_key') as mock_press:
        controller.adjust_line(error=5)
        mock_press.assert_not_called()

def test_key_duration_proportional_to_error(controller):
    """larger error → longer key press (up to max)"""
    with patch.object(controller, '_press_key') as mock_press:
        controller.adjust_line(error=50)
        _, dur50 = mock_press.call_args[0]
        mock_press.reset_mock()

        controller.adjust_line(error=100)
        _, dur100 = mock_press.call_args[0]

    assert dur100 > dur50

def test_press_cast_sends_f_key(controller):
    with patch.object(controller, '_press_key') as mock_press:
        controller.press_cast()
        mock_press.assert_called_once_with('f', 0.05)
```

- [ ] **步骤 2：运行测试确认失败**

```bash
uv run pytest tests/test_controller.py -v
```
预期：ImportError

- [ ] **步骤 3：实现 controller.py**

```python
# src/controller.py
import time
import win32api
import win32con
import config

# 虚拟键码映射
VK_MAP = {
    'f': 0x46,
    'a': 0x41,
    'd': 0x44,
}


def _make_lparam(vk: int, key_up: bool = False) -> int:
    """构造 PostMessage 所需的 lParam。"""
    scan = win32api.MapVirtualKey(vk, 0)
    lParam = (scan << 16) | 1
    if key_up:
        lParam |= (0xC0 << 24)
    return lParam


class FishingController:

    def __init__(self, hwnd: int):
        self.hwnd = hwnd

    def press_cast(self):
        """按 F 键（抛竿或确认上钩）。"""
        self._press_key('f', 0.05)

    def adjust_line(self, error: float):
        """
        根据误差调整玩家竖线位置。
        error > 0: 玩家偏右 → 按 A 向左
        error < 0: 玩家偏左 → 按 D 向右
        |error| <= DEAD_ZONE: 不动
        """
        if abs(error) <= config.DEAD_ZONE:
            return

        direction = 'a' if error > 0 else 'd'
        raw_ms = abs(error) * config.KEY_SCALE
        duration = max(config.KEY_MIN_DURATION,
                       min(raw_ms / 1000.0, config.KEY_MAX_DURATION))
        self._press_key(direction, duration)

    def _press_key(self, key: str, duration: float):
        """向游戏窗口发送按键（PostMessage，无需前台焦点）。"""
        vk = VK_MAP[key]
        lp_down = _make_lparam(vk, key_up=False)
        lp_up = _make_lparam(vk, key_up=True)
        win32api.PostMessage(self.hwnd, win32con.WM_KEYDOWN, vk, lp_down)
        time.sleep(duration)
        win32api.PostMessage(self.hwnd, win32con.WM_KEYUP, vk, lp_up)
```

- [ ] **步骤 4：运行测试确认通过**

```bash
uv run pytest tests/test_controller.py -v
```
预期：5 tests PASSED

- [ ] **步骤 5：Commit**

```bash
git add src/controller.py tests/test_controller.py
git commit -m "feat: add FishingController with PostMessage key injection"
```

---

## 任务 5：状态机主循环 main.py

**文件：**
- 创建：`src/main.py`

- [ ] **步骤 1：实现主循环状态机**

```python
# src/main.py
import threading
import time
import win32gui
import config
from src.capture import WindowCapture
from src.detector import StateDetector, GameState
from src.controller import FishingController


class FishingBot:

    def __init__(self):
        self.capturer = WindowCapture(config.GAME_WINDOW_TITLE)
        self.detector = StateDetector()
        self.controller: FishingController | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._state_log: str = "已停止"

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def toggle(self):
        if self._running:
            self.stop()
        else:
            self.start()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def status(self) -> str:
        return self._state_log

    def _loop(self):
        """主循环：状态机，约 30fps 运行。"""
        cast_at: float | None = None  # 上次抛竿时间
        fishing_started = False

        while self._running:
            frame = self.capturer.get_frame()
            if frame is None:
                self._state_log = "找不到游戏窗口"
                time.sleep(1.0)
                continue

            # 确保 controller 绑定到正确的 HWND
            if self.controller is None:
                self.controller = FishingController(self.capturer.hwnd)

            state = self.detector.detect_state(frame)

            if state == GameState.FISHING:
                fishing_started = True
                self._state_log = "钓鱼中"
                fl, fr, px = self.detector.detect_fishing_positions(frame)
                if fl is not None and fr is not None and px is not None:
                    error = px - (fl + fr) / 2
                    self.controller.adjust_line(error)

            elif state == GameState.BITE:
                self._state_log = "上钩！按F"
                self.controller.press_cast()
                time.sleep(0.3)  # 等待游戏响应

            else:  # IDLE
                if fishing_started:
                    # 钓鱼刚结束，等待后重新抛竿
                    self._state_log = "钓鱼结束，等待中"
                    fishing_started = False
                    cast_at = None
                    time.sleep(config.END_WAIT_SEC)
                    continue

                now = time.time()
                need_cast = (
                    cast_at is None or
                    (now - cast_at) > config.MAX_WAIT_SEC
                )
                if need_cast:
                    self._state_log = "抛竿中"
                    self.controller.press_cast()
                    cast_at = now
                    time.sleep(config.CAST_WAIT_SEC)
                else:
                    self._state_log = f"等待上钩 ({now - cast_at:.0f}s)"

            time.sleep(config.LOOP_INTERVAL)

        self._state_log = "已停止"
```

- [ ] **步骤 2：Commit**

```bash
git add src/main.py
git commit -m "feat: add FishingBot state machine main loop"
```

---

## 任务 6：系统托盘界面 tray.py

**文件：**
- 创建：`src/tray.py`
- 创建：`run.py`（程序入口）

- [ ] **步骤 1：实现 tray.py**

```python
# src/tray.py
import threading
import pystray
import keyboard
from PIL import Image, ImageDraw
import config
from src.main import FishingBot


def _make_icon(color: str) -> Image.Image:
    """创建 32×32 纯色圆形托盘图标。"""
    img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((4, 4, 28, 28), fill=color)
    return img


def run_tray():
    bot = FishingBot()

    def on_toggle(icon=None, item=None):
        bot.toggle()
        # 切换图标颜色
        icon.icon = _make_icon('green' if bot.is_running else 'gray')
        icon.title = f"NTE Fishing Bot — {bot.status}"

    def on_quit(icon, item):
        bot.stop()
        icon.stop()

    # 绑定热键
    keyboard.add_hotkey(config.TOGGLE_HOTKEY, lambda: on_toggle(icon=icon))

    icon = pystray.Icon(
        name="NTE Fishing Bot",
        icon=_make_icon('gray'),
        title="NTE Fishing Bot — 已停止",
        menu=pystray.Menu(
            pystray.MenuItem("开始/暂停", on_toggle, default=True),
            pystray.MenuItem("退出", on_quit),
        )
    )

    icon.run()
```

- [ ] **步骤 2：创建入口文件 run.py**

```python
# run.py
from src.tray import run_tray

if __name__ == "__main__":
    run_tray()
```

- [ ] **步骤 3：验证程序可以启动（不崩溃）**

```bash
uv run python run.py
```
预期：系统托盘出现灰色图标，右键可见菜单，按 F12 切换绿色/灰色

- [ ] **步骤 4：Commit**

```bash
git add src/tray.py run.py
git commit -m "feat: add system tray UI with F12 hotkey toggle"
```

---

## 任务 7：集成验证

- [ ] **步骤 1：运行全部测试**

```bash
uv run pytest tests/ -v
```
预期：所有测试 PASS，无 ERROR

- [ ] **步骤 2：实际游戏验证清单**

按顺序验证：
1. 启动程序：`uv run python run.py`，托盘出现灰色图标 ✓
2. 进入游戏钓鱼场景（不需要游戏在前台）
3. 按 F12 → 图标变绿 ✓
4. 观察约 1 秒内工具自动按 F 抛竿 ✓
5. 等待上钩（约 5-30 秒），工具自动检测并按 F ✓
6. 钓鱼小游戏中，A/D 自动保持竖线在绿色滑块内 ✓
7. 捕获成功/失败后自动重新抛竿 ✓
8. 按 F12 → 图标变灰，停止操作 ✓

- [ ] **步骤 3：若 PostMessage 按键无效（备用方案）**

如果游戏不响应 PostMessage，改用 `keyboard` 库（需要游戏在前台 1ms）：
在 `controller.py` 中将 `_press_key` 改为：
```python
def _press_key(self, key: str, duration: float):
    import keyboard
    keyboard.press(key)
    time.sleep(duration)
    keyboard.release(key)
```

- [ ] **步骤 4：最终 commit**

```bash
git add .
git commit -m "feat: complete NTE fishing bot implementation"
```

---

## 已知风险与应对

| 风险 | 应对 |
|------|------|
| PostMessage 无效（DirectInput）| 任务7步骤3：改用keyboard库 |
| 颜色阈值偏差（其他分辨率/画质）| 调整 config.py 中的 HSV 阈值 |
| 玩家竖线找不到 | 检查 MARKER_INNER_X_START/END 参数是否适配当前分辨率 |
| 上钩误检（BITE_V_THRESHOLD）| 调高阈值到 200+，或加入持续时间要求（连续3帧才触发）|
