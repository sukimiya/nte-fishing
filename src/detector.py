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

        return fish_left, fish_right, player_x

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
        return float(hsv[:, :, 2].mean()) > config.BITE_V_THRESHOLD

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
        """查找玩家竖线（黄白亮线），排除两侧图标区域。"""
        inner = bar_hsv[:, config.MARKER_INNER_X_START:config.MARKER_INNER_X_END]
        mask = (
            (inner[:, :, 0] >= config.MARKER_H_LOW) &
            (inner[:, :, 0] <= config.MARKER_H_HIGH) &
            (inner[:, :, 2] > config.MARKER_V_MIN)
        )
        cols = np.where(mask.any(axis=0))[0]
        if len(cols) == 0:
            return None

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
