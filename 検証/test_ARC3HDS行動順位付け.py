from types import SimpleNamespace
import unittest

from 検証.test_ARC3提出agent import _AGENT, _frame
from arcengine import GameState


class _RankedPredictionHDS:
    def __init__(self):
        self.inputs = []

    def 照会する(self, external_input):
        self.inputs.append(external_input)
        action = external_input.内容["作用"]["番号"]
        principle_id = f"p-{action}"
        predictions = []
        principles = []
        conflicts = []

        if action in (1, 2, 3, 4, 5, 7):
            principles.append({
                "原理識別子": principle_id,
                "状態": "適用範囲付き暫定原理",
                "採用状態": "有効",
                "結果経路": ["公開応答区分"],
                "条件経路群": [["作用前公開状態"], ["作用", "番号"]],
            })
            value = {
                1: "盤面変化",
                2: "盤面変化",
                3: "レベル進行",
                4: "盤面変化",
                5: "可視変化なし",
                7: "盤面変化",
            }[action]
            predictions.append({
                "原理参照": principle_id,
                "結果経路": ["公開応答区分"],
                "予測値": value,
            })

        if action == 1:
            # A prediction without an active supported principle is ignored.
            predictions[0]["原理参照"] = "missing"
        elif action == 2:
            # Multiple predicted values for the same target path are rejected.
            second = dict(predictions[0])
            second["原理参照"] = "p-2b"
            second["予測値"] = "レベル進行"
            principles.append({
                "原理識別子": "p-2b",
                "状態": "適用範囲付き暫定原理",
                "採用状態": "有効",
                "結果経路": ["公開応答区分"],
                "条件経路群": [["作用前公開状態"], ["作用", "番号"]],
            })
            predictions.append(second)
        elif action == 4:
            conflicts.append({"結果経路": ["公開応答区分"]})
        elif action == 7:
            principles[0]["採用状態"] = "無効"

        return SimpleNamespace(
            状態="断定保留",
            内容={
                "予測群": predictions,
                "競合群": conflicts,
                "有効原理群": principles,
            },
        )


class ARC3HDSActionRankingTests(unittest.TestCase):
    def test_only_unique_active_state_conditioned_reward_ranks_legal_actions(self):
        agent = _AGENT.MyAgent(
            card_id="card",
            game_id="game",
            agent_name="agent",
            ROOT_URL="http://offline",
            record=False,
            arc_env=None,
        )
        fake_hds = _RankedPredictionHDS()
        agent._hds = fake_hds
        frame = _frame(GameState.NOT_FINISHED)

        action = agent.choose_action([frame], frame)

        self.assertEqual(action.作用番号, 3)
        self.assertIn(action.作用番号, frame.available_actions)
        self.assertEqual(agent.hds_runtime_stats["状態照会数"], 1)
        self.assertEqual(agent.hds_runtime_stats["HDS候補作用照会数"], 6)
        self.assertEqual(agent.hds_runtime_stats["HDS応答区分候補数"], 2)
        self.assertEqual(agent.hds_runtime_stats["HDS優先選択適用数"], 1)
        self.assertEqual(
            [item.内容["作用"]["番号"] for item in fake_hds.inputs],
            [1, 2, 3, 4, 5, 7],
        )
        for item in fake_hds.inputs:
            self.assertEqual(item.対象系境界, "ARC3公開作用応答")
            self.assertEqual(
                set(item.内容),
                {"作用前公開状態", "作用"},
            )
            self.assertFalse(item.内容["作用"]["引数あり"])
            summary = item.内容["作用前公開状態"]
            self.assertEqual(summary["作用可能数"], 7)
            self.assertEqual(
                set(summary), {"作用可能数", "色種類数", "最多色占有帯"}
            )
            self.assertNotIn("game_id", summary)

    def test_target_path_conflict_blocks_hds_hint(self):
        result = SimpleNamespace(
            状態="断定保留",
            内容={
                "予測群": [{
                    "原理参照": "p",
                    "結果経路": ["公開応答区分"],
                    "予測値": "レベル進行",
                }],
                "競合群": [{"結果経路": ["公開応答区分"]}],
                "有効原理群": [{
                    "原理識別子": "p",
                    "状態": "適用範囲付き暫定原理",
                    "採用状態": "有効",
                    "結果経路": ["公開応答区分"],
                    "条件経路群": [["作用前公開状態"], ["作用", "番号"]],
                }],
            },
        )
        self.assertIsNone(_AGENT.MyAgent._HDS公開応答順位予測(result))


if __name__ == "__main__":
    unittest.main()
