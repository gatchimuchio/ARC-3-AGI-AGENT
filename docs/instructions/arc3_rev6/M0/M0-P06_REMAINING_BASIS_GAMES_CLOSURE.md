# M0-P06 — 残りBasis Game閉包

- Point ID: `M0-P06_REMAINING_BASIS_GAMES_CLOSURE`
- Depends on: M0-P05 PASS
- Next: `M0-P07_INITIAL_HORIZONTAL_SUBTRACTION`

## 目的

最初のgameで成立した同じAGI構造を、残りbasis gameへ拡張して全てWINする。

## 反復単位

```text
one basis game
→ targeted HDS analysis
→ capability delta
→ same product path integration
→ official sample run
→ minimal repair
→ WIN
```

## 必須作業

1. basis順序に従い一gameずつ処理する。
2. game固有差は観測依存parameter／Applicability Predicateで表現する。
3. 既存完遂gameを毎回regressionする。
4. keyboard-only、ACTION6-only、mixed、RESET、ACTION7、long-horizonを実行で覆う。
5. 新しい個別solver pathを作らない。

## Hard Exit

```text
all_basis_games_WIN = true
all_basis_levels_complete = true
mandatory_action_surfaces_executed = true
mandatory_observation_surfaces_preserved = true
manual_intervention_count = 0
parallel_agent_path_count = 0
completed_basis_regression_failures = 0
```

## 禁止

- game別shell
- game IDからMechanismSpec選択
- 完成行動列保存
- 複数gameを一つの曖昧Unitで処理

## Failure Routing

各gameの未閉包はM0-P03／P04／P05の責任へ局所的に戻す。全basis WIN前にM0-P07へ進まない。
