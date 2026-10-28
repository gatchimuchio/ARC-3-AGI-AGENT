"""CPU-only, public-observation exploratory ARC3 Agent; experimental, no HDS.

The official ARC Prize Starter's Agent interface is used under its MIT license;
see STARTER-MIT-LICENSE.txt. No game identifier or private state drives actions.
"""
from __future__ import annotations

from collections import Counter, deque
import hashlib
import json
import random
from threading import Lock
from typing import Any

from arcengine import FrameData, GameAction, GameState
from agents.agent import Agent

_ACTION_LOCK = Lock()


def _visible_frame(observation: FrameData) -> list[list[int]]:
    layers = observation.frame
    if not layers:
        return []
    board = layers[-1]
    if hasattr(board, "tolist"):
        board = board.tolist()
    if not board or not all(isinstance(row, (list, tuple)) for row in board):
        return []
    width = len(board[0])
    if not 0 < len(board) <= 64 or not 0 < width <= 64 or any(len(row) != width for row in board):
        return []
    if any(type(cell) is not int for row in board for cell in row):
        return []
    return [list(row) for row in board]


def _fingerprint(observation: FrameData) -> str:
    layers = [layer.tolist() if hasattr(layer, "tolist") else layer for layer in observation.frame]
    visible = {"state": observation.state.name, "levels": observation.levels_completed,
               "frame": layers, "legal": sorted(observation.available_actions or []),
               "full_reset": observation.full_reset, "win_levels": observation.win_levels}
    return hashlib.sha256(json.dumps(visible, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _guarded_fingerprint(observation: FrameData) -> str | None:
    try:
        values = observation.available_actions
        if not isinstance(values, (list, tuple)) or any(type(v) is not int for v in values):
            return None
        return _fingerprint(observation)
    except (TypeError, ValueError, AttributeError, OverflowError):
        return None


def _identity_key(observation: FrameData) -> tuple[str, str | None] | None:
    # Used only to reject stale/cross-environment dispatches, never for selection.
    game = observation.game_id
    token = observation.guid
    if type(game) is not str or (token is not None and type(token) is not str):
        return None
    return game, token


def _candidate_points(board: list[list[int]]) -> list[tuple[int, int]]:
    """Use visible component centers and boundary points; no game-specific rules."""
    if not board:
        return []
    h, w = len(board), len(board[0])
    seen: set[tuple[int, int]] = set()
    points: list[tuple[int, int]] = []
    for y in range(h):
        for x in range(w):
            if (x, y) in seen:
                continue
            color = board[y][x]
            queue = deque([(x, y)])
            seen.add((x, y))
            component = []
            while queue:
                cx, cy = queue.popleft()
                component.append((cx, cy))
                for nx, ny in ((cx-1,cy),(cx+1,cy),(cx,cy-1),(cx,cy+1)):
                    if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and board[ny][nx] == color:
                        seen.add((nx, ny))
                        queue.append((nx, ny))
            n = len(component)
            sx, sy = sum(v[0] for v in component), sum(v[1] for v in component)
            centroid = min(component, key=lambda p: ((p[0]*n-sx)**2+(p[1]*n-sy)**2,p[1],p[0]))
            anchors = (centroid, min(component), max(component))
            points.extend(anchors)
    return list(dict.fromkeys(points))


class MyAgent(Agent):
    """Choose from legal actions by observation-local exploration, without HDS."""

    MAX_ACTIONS = 79  # Starter uses <=, hence at most 80 dispatches.

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._rng = random.Random(31025)
        self._trials: Counter[tuple[str, int]] = Counter()
        self._unchanged: Counter[tuple[str, int]] = Counter()
        self._point_trials: Counter[tuple[str, tuple[int, int]]] = Counter()
        self._previous: tuple[str, int] | None = None
        self._pending: tuple[GameAction, dict[str, Any], str, tuple[str, str | None]] | None = None
        self._safe_stop = False

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        # Starter calls this on a dummy frame before obtaining the first real one.
        if self._safe_stop:
            return True
        observation = self.arc_env.observation_space if self.action_counter == 0 else latest_frame
        if observation is None or _identity_key(observation) is None:
            self._safe_stop = True
            return True
        if observation.state is GameState.WIN:
            return True
        if observation.state is GameState.NOT_PLAYED and self.action_counter > 0:
            self._safe_stop = True
            return True
        if observation.state in (GameState.NOT_PLAYED, GameState.GAME_OVER):
            return False
        if observation.state is not GameState.NOT_FINISHED:
            return True
        if any(type(value) is not int for value in (observation.available_actions or [])):
            self._safe_stop = True
            return True
        legal = {value for value in (observation.available_actions or [])
                 if type(value) is int and 1 <= value <= 7}
        if legal == {6} and not _visible_frame(observation):
            legal.clear()
        if not legal:
            self._safe_stop = True
            return True
        return False

    def choose_action(self, frames: list[FrameData], latest_frame: FrameData) -> GameAction | None:
        identity = _identity_key(latest_frame)
        if identity is None:
            self._safe_stop = True
            self._pending = None
            return None
        if latest_frame.state is GameState.NOT_PLAYED and self.action_counter > 0:
            self._safe_stop = True
            self._pending = None
            return None
        signature = _guarded_fingerprint(latest_frame)
        if signature is None:
            self._safe_stop = True
            self._pending = None
            return None
        if latest_frame.state in (GameState.NOT_PLAYED, GameState.GAME_OVER):
            self._previous = None
            self._pending = (GameAction.RESET, {}, signature, identity)
            return GameAction.RESET
        if latest_frame.state is not GameState.NOT_FINISHED:
            self._safe_stop = True
            self._pending = None
            return None
        legal = sorted({value for value in (latest_frame.available_actions or [])
                        if type(value) is int and 1 <= value <= 7})
        board = _visible_frame(latest_frame)
        points = _candidate_points(board) if 6 in legal else []
        if 6 in legal and not points:
            legal.remove(6)
        if not legal:
            self._safe_stop = True
            self._pending = None
            return None
        state = signature
        if self._previous is not None and self._previous[0] == state:
            self._unchanged[self._previous] += 1
        keys = {a: (self._trials[(state, a)] + self._unchanged[(state, a)], self._trials[(state, a)]) for a in legal}
        minimum = min(keys.values())
        chosen = self._rng.choice([a for a in legal if keys[a] == minimum])
        self._trials[(state, chosen)] += 1
        self._previous = (state, chosen)
        action = GameAction.from_id(chosen)
        data: dict[str, Any] = {}
        if chosen == 6:
            least = min(self._point_trials[(state, p)] for p in points)
            point = self._rng.choice([p for p in points if self._point_trials[(state, p)] == least])
            self._point_trials[(state, point)] += 1
            data = {"x": point[0], "y": point[1]}
        self._pending = (action, data, state, identity)
        return action

    def take_action(self, action: GameAction | None):
        # No side effect is performed when the pending action or observation is stale.
        if self._pending is None or action is None or self._pending[0] is not action:
            self._pending = None
            self._safe_stop = True
            return None
        _, data, expected, expected_identity = self._pending
        self._pending = None
        with _ACTION_LOCK:
            observation = self.arc_env.observation_space
            if observation is None or _identity_key(observation) != expected_identity or _guarded_fingerprint(observation) != expected:
                self._safe_stop = True
                return None
            if action is GameAction.RESET:
                if observation.state not in (GameState.NOT_PLAYED, GameState.GAME_OVER):
                    self._safe_stop = True
                    return None
            else:
                legal = {value for value in (observation.available_actions or [])
                         if type(value) is int and 1 <= value <= 7}
                if observation.state is not GameState.NOT_FINISHED or action.value not in legal:
                    self._safe_stop = True
                    return None
                if action is GameAction.ACTION6:
                    board = _visible_frame(observation)
                    x, y = data.get("x"), data.get("y")
                    if not board or type(x) is not int or type(y) is not int or not (0 <= y < len(board) and 0 <= x < len(board[y])):
                        self._safe_stop = True
                        return None
            # GameAction is a process-wide mutable Enum; protect data mutation and step.
            action.set_data(data)
            return super().take_action(action)
