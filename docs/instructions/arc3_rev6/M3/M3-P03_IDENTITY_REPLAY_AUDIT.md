# M3-P03 — Identity／Replay Audit

- Point ID: `M3-P03_IDENTITY_REPLAY_AUDIT`
- Depends on: M3-P02 PASS
- Next: `M3-P04_APPLICABILITY_COUNTERFACTUAL`

## 目的

full-sample完遂がidentity lookup、固定軌道、exact frame routeに依存しないことを確認する。

## Audit Scope

```text
product code
PBundle／P-IR
JDomainProfile
M0／initial state
Runtime M seed
MechanismSpec／Domain-Local Residue
selectors／bindings
package contents
```

## Forbidden Flow

```text
game_id／level_id → decision feature
recording_id／trajectory_id → mechanism selection
exact frame hash → next action
successful action index → action
complete action sequence storage
replay guard → runtime execution
```

## 必須作業

1. static scanだけでなくdata flowを追跡する。
2. orchestration metadataをtaintとしてdecision boundaryで遮断する。
3. replay関連記述とruntime execute eligibilityを照合する。
4. findingを観測依存Applicabilityへ置換する。
5. M2 A／B／Cを再回帰する。

## Hard Exit

```text
identity_action_router_finding_count = 0
fixed_trajectory_playback_finding_count = 0
exact_frame_action_lookup_count = 0
runtime_replay_guard_count = 0
complete_action_sequence_runtime_count = 0
M2_regression = PASS
```

## 禁止

- `runtime_selector = NONE`という自己申告だけでPASS
- description内のreplay記述を無視
- package外にlookupを移して監査回避

## Failure Routing

findingが一つでもあれば修正後に全scopeを再監査する。
