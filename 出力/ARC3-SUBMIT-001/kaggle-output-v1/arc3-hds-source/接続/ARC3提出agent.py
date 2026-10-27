"""現行のHDS候補を確定扱いせず停止する、初回提出用の棄権基線。

最初の公開観測がNOT_PLAYEDなら、RESETを一度だけ送り次のFrameを取得する。
SDKが最初からNOT_FINISHEDを返す場合は何も送らず、観測をHDS候補経路へ渡して終了する。
現行repoに作用認可発行元がないため、追加のGameActionは返さない。
"""
from __future__ import annotations

import logging
from typing import Any

from agents.agent import Agent
from arcengine import FrameData, GameAction, GameState
from hds学習系統 import HDS学習系統

from 接続.ARC3境界 import 境界違反, 観測する
from 接続.共通観測経路 import 公開観測から候補を照会する

_LOG = logging.getLogger(__name__)


class MyAgent(Agent):
    """公開観測を候補照会し、未認可候補では直ちに終了する。"""

    MAX_ACTIONS = 1

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._hds = HDS学習系統()
        self._last_hold: dict[str, Any] | None = None

    @property
    def last_hold(self) -> dict[str, Any] | None:
        """試験・診断向けの要約。盤面、秘密、候補内容は保持しない。"""
        return None if self._last_hold is None else dict(self._last_hold)

    def _現在のSDK観測(self, fallback: FrameData) -> FrameData | None:
        if self.arc_env is None:
            return fallback
        raw = getattr(self.arc_env, "observation_space", None)
        if raw is None:
            return None
        return self._convert_raw_frame_data(raw)

    def _HDS照会後に停止する(self, frames: list[FrameData], frame: FrameData) -> None:
        try:
            observation = 観測する(frame, 観測通番=max(0, len(frames) - 1))
            candidate = 公開観測から候補を照会する(self._hds, observation)
            self._last_hold = {
                "状態": "HOLD",
                "観測指紋": observation.指紋,
                "候補経路状態": candidate.get("状態"),
                "次作用候補数": len(candidate.get("次作用候補群", [])),
                "候補側申告実行許可": candidate.get("実行許可") is True,
            }
            _LOG.info(
                "ARC3 baseline HOLD: candidate_state=%s candidate_count=%d permission_claim=%s",
                self._last_hold["候補経路状態"],
                self._last_hold["次作用候補数"],
                self._last_hold["候補側申告実行許可"],
            )
        except Exception as exc:
            self._last_hold = {
                "状態": "HOLD",
                "理由": type(exc).__name__,
                "候補側申告実行許可": False,
            }
            _LOG.warning("ARC3 baseline HOLD: observation query failed (%s)", type(exc).__name__)

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        if latest_frame.state is GameState.WIN:
            return True

        # Agent.main checks its placeholder frame before passing the current SDK observation
        # to choose_action. Inspect the SDK observation here to avoid forcing a RESET or move.
        if latest_frame.state is GameState.NOT_PLAYED and self.action_counter == 0:
            current = self._現在のSDK観測(latest_frame)
            if current is None:
                self._last_hold = {
                    "状態": "HOLD",
                    "理由": "初回SDK観測欠落",
                    "候補側申告実行許可": False,
                }
                return True
            if current.state is GameState.NOT_PLAYED:
                return False
            if current.state is GameState.NOT_FINISHED:
                self._HDS照会後に停止する(frames, current)
            return True

        if latest_frame.state is GameState.NOT_FINISHED:
            self._HDS照会後に停止する(frames, latest_frame)
        return True

    def choose_action(
        self, frames: list[FrameData], latest_frame: FrameData
    ) -> GameAction:
        if latest_frame.state is GameState.NOT_PLAYED and self.action_counter == 0:
            return GameAction.RESET
        raise 境界違反("現行HDS確定作用がないため、初期化以外のActionは返せません。")

