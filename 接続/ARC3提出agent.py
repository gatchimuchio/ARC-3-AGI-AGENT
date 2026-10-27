"""HDS-HOLDと分離した公開観測ベースのARC3探索agent。"""
from __future__ import annotations

import logging
import time
from typing import Any

from agents.agent import Agent
from arcengine import FrameData, GameAction, GameState

from 接続.ARC3境界 import 境界違反, 観測, 観測する
from 接続.共通観測経路 import 公開観測から候補を照会する
from 接続.観測駆動探索Action import 探索Action, 観測駆動探索方針
from 接続.ARC3事前記憶 import 事前記憶をHDSへ供給する
from hds学習系統 import HDS学習系統
from hds学習系統.型 import 外部入力

_LOG = logging.getLogger(__name__)


class MyAgent(Agent):
    """探索Actionの出所をHDS候補・確定Actionから分離して実行する。"""

    # Agent.main uses <=, so 79 permits at most 80 actual action requests.
    MAX_ACTIONS = 79

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._hds = HDS学習系統()
        self._hds_prior_report = 事前記憶をHDSへ供給する(self._hds)
        self._policy = 観測駆動探索方針(
            可視変化係数=self._hds_prior_report["visible_change_coefficient"]
        )
        self._last_hold: dict[str, Any] | None = None
        self._pending: tuple[観測, 探索Action] | None = None
        self._observation_counter = 0
        self._used_observations: set[str] = set()
        self._safe_stop = False
        self._hds_scope_game: str | None = None
        self._hds_updates = 0
        self._hds_queries = 0
        self._hds_last_learning_state: str | None = None
        self._hds_last_query_state: str | None = None
        self._hds_update_seconds = 0.0
        self._hds_query_seconds = 0.0
        self._hds_candidate_query_seconds = 0.0
        self._hds_candidate_action_queries = 0
        self._hds_predicted_outcome_candidates = 0
        self._hds_guided_action_selections = 0

    @property
    def last_hold(self) -> dict[str, Any] | None:
        """試験・診断向けのHDS要約。盤面や候補内容は保持しない。"""
        return None if self._last_hold is None else dict(self._last_hold)

    @property
    def exploration_stats(self) -> dict[int, dict[str, float | int]]:
        return self._policy.統計()

    @property
    def hds_runtime_stats(self) -> dict[str, Any]:
        """HDSの更新・照会件数だけを返す。盤面やゲームIDは公開しない。"""
        return {
            "観測更新数": self._hds_updates,
            "状態照会数": self._hds_queries,
            "最終学習状態": self._hds_last_learning_state,
            "最終照会状態": self._hds_last_query_state,
            "学習累計秒": round(self._hds_update_seconds, 6),
            "状態照会累計秒": round(self._hds_query_seconds, 6),
            "語彙候補照会累計秒": round(self._hds_candidate_query_seconds, 6),
            "HDS候補作用照会数": self._hds_candidate_action_queries,
            "HDS応答区分候補数": self._hds_predicted_outcome_candidates,
            "HDS優先選択適用数": self._hds_guided_action_selections,
            "事前記憶版": self._hds_prior_report["version"],
            "事前記憶読込件数": self._hds_prior_report["loaded_count"],
            "事前記憶HDS境界": self._hds_prior_report["boundary"],
            "事前記憶Action認可": self._hds_prior_report["action_authorization"],
            "事前記憶反映可視変化係数": self._hds_prior_report["visible_change_coefficient"],
        }

    def _HDS適用範囲を保つ(self, observed: 観測) -> None:
        # 公開game_idは状態の混線を防ぐ区切りだけに使い、Action選択には使わない。
        if self._hds_scope_game is None:
            self._hds_scope_game = observed.ゲーム識別子
        elif self._hds_scope_game != observed.ゲーム識別子:
            self._hds = HDS学習系統()
            self._hds_prior_report = 事前記憶をHDSへ供給する(self._hds)
            self._hds_scope_game = observed.ゲーム識別子
            self._hds_updates = 0
            self._hds_queries = 0
            self._hds_last_learning_state = None
            self._hds_last_query_state = None
            self._hds_update_seconds = 0.0
            self._hds_query_seconds = 0.0
            self._hds_candidate_query_seconds = 0.0
            self._hds_candidate_action_queries = 0
            self._hds_predicted_outcome_candidates = 0
            self._hds_guided_action_selections = 0

    @staticmethod
    def _HDS作用前状態(observed: 観測) -> dict[str, Any]:
        board = observed.最新盤面
        color_counts: dict[int, int] = {}
        for row in board:
            for color in row:
                color_counts[color] = color_counts.get(color, 0) + 1
        area = max(1, sum(len(row) for row in board))
        majority_share = max(color_counts.values(), default=0) / area
        occupancy_band = (
            "低"
            if majority_share < 0.25
            else "中低"
            if majority_share < 0.5
            else "中高"
            if majority_share < 0.75
            else "高"
        )
        # Coarse, task-agnostic public features are available to each fresh
        # game instance and avoid storing board cells or game identifiers.
        return {
            "作用可能数": len(observed.作用可能番号),
            "色種類数": len(color_counts),
            "最多色占有帯": occupancy_band,
        }

    @staticmethod
    def _HDS公開応答順位予測(result: Any) -> int | None:
        content = getattr(result, "内容", None)
        if (
            not isinstance(content, dict)
            or getattr(result, "状態", None) not in ("出力", "断定保留")
        ):
            return None
        path = ("公開応答区分",)
        conflicts = content.get("競合群", ())
        if any(
            isinstance(item, dict)
            and tuple(item.get("結果経路", ())) == path
            for item in conflicts
        ):
            return None
        active_principles = {
            item.get("原理識別子")
            for item in content.get("有効原理群", ())
            if isinstance(item, dict)
            and tuple(item.get("結果経路", ())) == path
            and item.get("状態") == "適用範囲付き暫定原理"
            and item.get("採用状態") == "有効"
            and any(
                tuple(condition)[:1] == ("作用前公開状態",)
                for condition in item.get("条件経路群", ())
            )
            and any(
                tuple(condition) == ("作用", "番号")
                for condition in item.get("条件経路群", ())
            )
        }
        values = {
            item.get("予測値")
            for item in content.get("予測群", ())
            if isinstance(item, dict)
            and tuple(item.get("結果経路", ())) == path
            and item.get("原理参照") in active_principles
            and item.get("予測値") in ("可視変化なし", "盤面変化", "レベル進行", "勝利")
        }
        if len(values) != 1:
            return None
        return {
            "可視変化なし": 0,
            "盤面変化": 1,
            "レベル進行": 2,
            "勝利": 3,
        }[next(iter(values))]

    def _HDS状態を照会する(self, observed: 観測) -> tuple[int, ...]:
        self._HDS適用範囲を保つ(observed)
        started = time.perf_counter()
        predicted_outcome: dict[int, int] = {}
        self._hds_queries += 1
        try:
            # HDS ranks only legal non-coordinate actions with an active,
            # nonconflicting reward rule conditioned on public state and action.
            # Action 6 is omitted because its record does not include selected x/y.
            for action_number in sorted(set(observed.作用可能番号)):
                if type(action_number) is not int or not 1 <= action_number <= 7 or action_number == 6:
                    continue
                self._hds_candidate_action_queries += 1
                try:
                    result = self._hds.照会する(
                        外部入力(
                            {
                                "作用前公開状態": self._HDS作用前状態(observed),
                                "作用": {"番号": action_number, "引数あり": False},
                            },
                            "ARC3公開作用応答",
                            目的="公開状態と合法作用に対する既学習公開応答区分の順位照会。Action認可には不使用",
                        )
                    )
                    self._hds_last_query_state = result.状態
                    outcome_rank = self._HDS公開応答順位予測(result)
                    if outcome_rank is not None:
                        predicted_outcome[action_number] = outcome_rank
                except Exception as exc:
                    self._hds_last_query_state = f"ERROR:{type(exc).__name__}"
                    _LOG.warning("ARC3 HDS action ranking query failed (%s)", type(exc).__name__)
            if not predicted_outcome:
                return ()
            best_outcome_rank = max(predicted_outcome.values())
            preferred = tuple(
                action_number
                for action_number in sorted(predicted_outcome)
                if predicted_outcome[action_number] == best_outcome_rank
            )
            self._hds_predicted_outcome_candidates += len(predicted_outcome)
            return preferred
        finally:
            self._hds_query_seconds += time.perf_counter() - started

    def _HDS作用応答を学ぶ(
        self,
        before: 観測,
        action: 探索Action,
        after: 観測,
    ) -> None:
        self._HDS適用範囲を保つ(before)
        if before.ゲーム識別子 != after.ゲーム識別子:
            _LOG.warning("ARC3 HDS update skipped across a public game boundary")
            return
        # Store only pre-action public context, the legal action, and its
        # observed outcome. Post-state and game-specific board content are not
        # query conditions and would multiply HDS's inference workload.
        if after.状態 == "WIN":
            outcome = "勝利"
        elif after.完了レベル数 > before.完了レベル数:
            outcome = "レベル進行"
        elif after.最新盤面 != before.最新盤面:
            outcome = "盤面変化"
        else:
            outcome = "可視変化なし"
        content = {
            "作用前公開状態": self._HDS作用前状態(before),
            "作用": {
                "番号": action.作用番号,
                "引数あり": bool(action.引数),
            },
            "公開応答区分": outcome,
        }
        started = time.perf_counter()
        try:
            result = self._hds.処理する(
                外部入力(
                    content,
                    "ARC3公開作用応答",
                    目的="公開観測された遷移と方針報酬の記録。因果や成功規則を仮定しない",
                )
            )
            self._hds_updates += 1
            self._hds_last_learning_state = result.状態
        except Exception as exc:
            self._hds_last_learning_state = f"ERROR:{type(exc).__name__}"
            _LOG.warning("ARC3 HDS transition update failed (%s)", type(exc).__name__)
        finally:
            self._hds_update_seconds += time.perf_counter() - started

    def _現在のSDK観測(self, fallback: FrameData) -> FrameData | None:
        if self.arc_env is None:
            return fallback
        raw = getattr(self.arc_env, "observation_space", None)
        if raw is None:
            return None
        return self._convert_raw_frame_data(raw)

    def _HDS照会後に停止しない(self, frames: list[FrameData], frame: FrameData) -> None:
        """HDS HOLDを独立診断として記録する。探索Actionの認可には使わない。"""
        try:
            observation = 観測する(frame, 観測通番=max(0, len(frames) - 1))
            self._HDS適用範囲を保つ(observation)
            started = time.perf_counter()
            candidate = 公開観測から候補を照会する(self._hds, observation)
            self._hds_candidate_query_seconds += time.perf_counter() - started
            self._last_hold = {
                "状態": "HOLD",
                "観測指紋": observation.指紋,
                "候補経路状態": candidate.get("状態"),
                "次作用候補数": len(candidate.get("次作用候補群", [])),
                "候補側申告実行許可": candidate.get("実行許可") is True,
                "探索Actionとの関係": "独立・認可に不使用",
            }
            _LOG.info(
                "ARC3 HDS diagnostic HOLD: candidate_state=%s candidate_count=%d",
                self._last_hold["候補経路状態"],
                self._last_hold["次作用候補数"],
            )
        except Exception as exc:
            self._last_hold = {
                "状態": "HOLD",
                "理由": type(exc).__name__,
                "候補側申告実行許可": False,
                "探索Actionとの関係": "独立・認可に不使用",
            }
            _LOG.warning("ARC3 HDS diagnostic HOLD (%s)", type(exc).__name__)

    @staticmethod
    def _状態(frame: FrameData) -> str:
        value = frame.state
        return getattr(value, "name", str(value))

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        if self._safe_stop or self.action_counter > self.MAX_ACTIONS:
            return True
        state = self._状態(latest_frame)
        if state == "WIN":
            return True
        if state == "GAME_OVER":
            return False

        if state == "NOT_PLAYED" and self.action_counter == 0:
            current = self._現在のSDK観測(latest_frame)
            if current is None:
                self._safe_stop = True
                return True
            current_state = self._状態(current)
            if current_state in ("WIN", "GAME_OVER"):
                return True
            if current_state not in ("NOT_PLAYED", "NOT_FINISHED"):
                self._safe_stop = True
                return True
            if current_state == "NOT_FINISHED":
                try:
                    observed = 観測する(current, 観測通番=self._observation_counter)
                except 境界違反 as exc:
                    self._last_hold = {"状態": "HOLD", "理由": type(exc).__name__}
                    self._safe_stop = True
                    return True
                if not observed.作用可能番号:
                    return True
                if self._last_hold is None:
                    self._HDS照会後に停止しない(frames, current)
                return False
            return False

        if state == "NOT_FINISHED":
            try:
                observed = 観測する(latest_frame, 観測通番=self._observation_counter)
            except 境界違反 as exc:
                self._last_hold = {"状態": "HOLD", "理由": type(exc).__name__}
                self._safe_stop = True
                return True
            if not observed.作用可能番号:
                return True
            if self._last_hold is None:
                self._HDS照会後に停止しない(frames, latest_frame)
            return False

        # The official starter permits RESET after GAME_OVER as a new play.
        return True

    def choose_action(
        self, frames: list[FrameData], latest_frame: FrameData
    ) -> 探索Action:
        if self._safe_stop:
            raise 境界違反("安全停止中はActionを選べない")
        if self._pending is not None:
            raise 境界違反("前Actionの応答観測前に次Actionを選べない")
        observed = 観測する(latest_frame, 観測通番=self._observation_counter)
        hds_preferred_actions = ()
        if observed.状態 != "NOT_PLAYED":
            hds_preferred_actions = self._HDS状態を照会する(observed)
        if observed.指紋 in self._used_observations:
            raise 境界違反("同一観測に二度作用できない")
        action = self._policy.選ぶ(
            observed, HDS優先作用番号群=hds_preferred_actions
        )
        if action is None:
            raise 境界違反("公開観測から合法な探索Actionを構成できない")
        if action.作用番号 in hds_preferred_actions:
            self._hds_guided_action_selections += 1
        if action.作用番号 == 0 and not (
            action.出所 == "SDKリセット"
            and (
                observed.状態 == "GAME_OVER"
                or observed.状態 == "NOT_PLAYED" and self.action_counter == 0
            )
        ):
            raise 境界違反("RESETは初回NOT_PLAYEDまたはGAME_OVERからのみ許可")
        if action.作用番号 != 0 and action.出所 != "観測駆動探索":
            raise 境界違反("ゲームActionの出所が探索ではない")
        self._pending = (observed, action)
        return action

    def do_action_request(self, action: 探索Action) -> FrameData:
        """最新のSDK観測・合法集合・座標を再照合して一回だけ送信する。"""
        if not isinstance(action, 探索Action) or self._pending is None:
            raise 境界違反("探索出所のないActionをSDKへ送れない")
        before, pending_action = self._pending
        if action != pending_action:
            raise 境界違反("送信Actionが現在観測の探索判断と一致しない")
        if before.指紋 in self._used_observations:
            raise 境界違反("同一観測に二度作用できない")
        if self.arc_env is None:
            raise 境界違反("SDK環境がないため探索Actionを送れない")

        raw_current = getattr(self.arc_env, "observation_space", None)
        if raw_current is None:
            raise 境界違反("作用前のSDK観測がない")
        current_frame = self._convert_raw_frame_data(raw_current)
        current = 観測する(current_frame, 観測通番=before.観測通番)
        if current.指紋 != before.指紋:
            raise 境界違反("作用前にSDK観測が変化した")
        if action.作用番号 != 0 and action.作用番号 not in current.作用可能番号:
            raise 境界違反("探索Actionが最新available_actionsにない")
        if action.作用番号 == 0 and not (
            action.出所 == "SDKリセット"
            and (
                current.状態 == "GAME_OVER"
                or current.状態 == "NOT_PLAYED" and self.action_counter == 0
            )
        ):
            raise 境界違反("RESETは初回NOT_PLAYEDまたはGAME_OVERからのみ許可")
        if action.作用番号 != 0 and action.出所 != "観測駆動探索":
            raise 境界違反("ゲームActionの出所が探索ではない")
        if action.作用番号 == 6:
            if set(action.引数) != {"x", "y"}:
                raise 境界違反("座標Actionにx,yが必要")
            for key in ("x", "y"):
                value = action.引数[key]
                if type(value) is not int or not 0 <= value <= 63:
                    raise 境界違反("座標Actionが公式範囲外")
        elif action.引数:
            raise 境界違反("単純Actionに引数を付けられない")

        self._used_observations.add(before.指紋)
        raw_after = self.arc_env.step(
            GameAction.from_id(action.作用番号),
            data=dict(action.引数),
            reasoning={"Action出所": action.出所, "作用前観測指紋": before.指紋},
        )
        if raw_after is None:
            self._safe_stop = True
            raise 境界違反("SDKから公開応答を取得できない")
        frame = FrameData.model_validate(self._convert_raw_frame_data(raw_after))
        after = 観測する(frame, 観測通番=before.観測通番 + 1)
        if action.作用番号 != 0:
            receipt = self._policy.応答を記録する(before, action, after)
            self._HDS作用応答を学ぶ(before, action, after)
            _LOG.debug("ARC3 exploratory response: %s", receipt)
        self._observation_counter = before.観測通番 + 1
        self._pending = None
        return frame
