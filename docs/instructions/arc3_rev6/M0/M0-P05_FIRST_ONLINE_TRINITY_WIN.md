# M0-P05 — 最初のOnline Trinity WIN

- Point ID: `M0-P05_FIRST_ONLINE_TRINITY_WIN`
- Depends on: M0-P04 PASS
- Next: `M0-P06_REMAINING_BASIS_GAMES_CLOSURE`
- Official sample execution: 必須

## 目的

最初のbasis gameを、人間の一手指示なしにC／J／Mオンライン循環でWINする。

## 必須循環

```text
OBSERVE
→ F
→ C: multiple models/plans
→ J: select/probe/wait
→ one authorized action
→ OBSERVE RESULT
→ G11 attribution
→ M update
→ revised next model/plan/action
```

## 必須作業

1. first basis gameをactual official sample environmentで実行する。
2. 全外部actionのJ authorizationを記録する。
3. failureまたはno-effect後にMを更新する。
4. relevant M更新で次の候補／計画／actionが変わることを示す。
5. 同じ失敗仮説の無限反復を防ぐ。
6. WINまでCapability Closure Unitを反復する。

## Hard Exit

```text
first_basis_game_final_state = WIN
all_levels_complete = true
manual_step_intervention_count = 0
J_bypass_count = 0
relevant_M_behavior_change_count > 0
failed_hypothesis_repetition_is_bounded = true
fixed_trajectory_playback_count = 0
```

mock／synthetic／teacher replayだけではPASS不可。

## Failure Routing

- representation／mechanism／plan不足 → M0-P04へ戻る
- HDS採否不足 → J_dev修正
- memory因果不足 → M_dev修正
- 解析誤り → M0-P03へ戻る
