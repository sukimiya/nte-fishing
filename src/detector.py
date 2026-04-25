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
        if self._is_bar_visible(frame):
            return GameState.FISHING
        if self._is_bite(frame):
            return GameState.BITE
        return GameState.IDLE

    def detect_fishing_positions(self, frame: np.ndarray) -> tuple[int | None, int | None, int | None]:
        """返回 (fish_left, fish_right, player_x)，bar region 坐标系，找不到时对应值为 None。"""
        h, w = frame.shape[:2]
        bx1 = int(w * config.BAR_X_START_RATIO)
        bx2 = int(w * config.BAR_X_END_RATIO)
        by1 = int(h * config.BAR_Y_START_RATIO)
        by2 = int(h * config.BAR_Y_END_RATIO)

        bar = frame[by1:by2, bx1:bx2]
        hsv = cv2.cvtColor(bar, cv2.COLOR_BGR2HSV)

        fish_left, fish_right = self._find_slider(hsv)
        player_x = self._find_player_marker(hsv)

        # 过滤假阳性：竖线距鱼滑块中心超过 400px 视为误检
        if fish_left is not None and fish_right is not None and player_x is not None:
            fish_center = (fish_left + fish_right) / 2
            if abs(player_x - fish_center) > config.PLAYER_MAX_DIST_FROM_FISH:
                player_x = None

        return fish_left, fish_right, player_x

    def _is_bar_visible(self, frame: np.ndarray) -> bool:
        h, w = frame.shape[:2]
        bar = frame[
            int(h * config.BAR_Y_START_RATIO):int(h * config.BAR_Y_END_RATIO),
            int(w * config.BAR_X_START_RATIO):int(w * config.BAR_X_END_RATIO)
        ]
        hsv = cv2.cvtColor(bar, cv2.COLOR_BGR2HSV)
        mask = self._slider_mask(hsv)
        return int(mask.sum()) > config.SLIDER_PX_THRESHOLD

    def _is_bite(self, frame: np.ndarray) -> bool:
        h, w = frame.shape[:2]
        icon = frame[
            int(h * config.HOOK_Y_START_RATIO):int(h * config.HOOK_Y_END_RATIO),
            int(w * config.HOOK_X_START_RATIO):int(w * config.HOOK_X_END_RATIO)
        ]
        hsv = cv2.cvtColor(icon, cv2.COLOR_BGR2HSV)
        blue_mask = (
            (hsv[:, :, 0] >= config.BITE_BLUE_H_LOW) &
            (hsv[:, :, 0] <= config.BITE_BLUE_H_HIGH) &
            (hsv[:, :, 1] > config.BITE_BLUE_S_MIN) &
            (hsv[:, :, 2] > config.BITE_BLUE_V_MIN)
        )
        return int(blue_mask.sum()) > config.BITE_BLUE_PX_THRESHOLD

    def _slider_mask(self, hsv: np.ndarray) -> np.ndarray:
        return (
            (hsv[:, :, 0] >= config.SLIDER_H_LOW) &
            (hsv[:, :, 0] <= config.SLIDER_H_HIGH) &
            (hsv[:, :, 1] > config.SLIDER_S_MIN) &
            (hsv[:, :, 2] > config.SLIDER_V_MIN)
        )

    def _find_slider(self, bar_hsv: np.ndarray) -> tuple[int | None, int | None]:
        mask = self._slider_mask(bar_hsv)
        cols = np.where(mask.any(axis=0))[0]
        if len(cols) == 0:
            return None, None
        # 分组为连续段，取最宽的段（右侧常有1-4px虚假段）
        segments: list[tuple[int, int]] = []
        s = p = int(cols[0])
        for c in cols[1:]:
            if c - p > 5:
                segments.append((s, p))
                s = int(c)
            p = int(c)
        segments.append((s, p))
        best = max(segments, key=lambda g: g[1] - g[0])
        return best[0], best[1]

    def _find_player_marker(self, bar_hsv: np.ndarray) -> int | None:
        """查找玩家竖线（黄白亮线），排除两侧图标区域。"""
        bar_w = bar_hsv.shape[1]
        ix0 = int(bar_w * config.MARKER_INNER_X_START_RATIO)
        ix1 = int(bar_w * config.MARKER_INNER_X_END_RATIO)
        inner = bar_hsv[:, ix0:ix1]
        mask = (
            (inner[:, :, 0] >= config.MARKER_H_LOW) &
            (inner[:, :, 0] <= config.MARKER_H_HIGH) &
            (inner[:, :, 2] > config.MARKER_V_MIN)
        )
        cols = np.where(mask.any(axis=0))[0]
        if len(cols) == 0:
            return None
        if len(cols) == 1:
            return int(cols[0]) + ix0

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
        return int(np.mean(best)) + ix0
