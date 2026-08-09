# M0-P02 — Basis Set選定

- Point ID: `M0-P02_BASIS_SET_SELECTION`
- Depends on: M0-P01 PASS
- Next: `M0-P03_FIRST_BASIS_GAME_HDS_ANALYSIS`

## 目的

最小のgame集合で、最初のAGI能力基底に必要なsurfaceを覆う。

## 必須Coverage

```text
keyboard-only
ACTION6-only
mixed action surface
RESET
ACTION7
multi-layer or temporal complexity
long-horizon resource
rollback/game-over recovery
nontrivial goal or phase structure
```

## 選定評価

各候補を次で比較する。

```text
coverage contribution
overlap with selected games
first vertical closure feasibility
mechanism diversity
planning depth
regression value
```

## 必須作業

1. Matrixから候補を選ぶ。
2. 各選定gameのcoverage責任を明記する。
3. 非選定の近接候補より優先する理由を書く。
4. first basis gameを一つ指定する。
5. 未被覆surfaceがあれば追加game条件を明示する。

## 出力

`analysis/product/rev6/basis_set_selection.json`

## Hard Exit

```text
all mandatory surfaces covered
first_basis_game fixed
basis execution order fixed
selection based on capability coverage
no action-sequence convenience criterion
```

## 禁止

- 短いgameだけに偏る
- 同一mechanism familyだけで構成
- 答え列を使いやすいことを選定理由にする
- 解析・実装の先行

## Failure Routing

未被覆surfaceが残る場合はbasisを追加・交換し、Hard ExitまでM0-P02を閉じない。
