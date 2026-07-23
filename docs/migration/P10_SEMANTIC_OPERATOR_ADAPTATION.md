# P10 identity-free意味演算子 移植監査

- classification: `ADAPT`
- target phase: `P10_COMPLETE_ARC3_SAMPLE_SOLVING`
- active runtime import from legacy repo: `none`
- HDS judgment: `PASS` for the bounded operator block / `HOLD` for P10

## 1. Work-block契約

```text
X:
  rendered grid、available action、P内のversioned operator instruction、
  HDS承認済みM内のplanner queue

R:
  Pがdetector/transform/parameterを供給
  -> Cがrendered relation latticeを検出して制約を解く
  -> Jが候補を採否
  -> 承認済みactionをemit
  -> 結果観測後にM queueを更新または失敗planを無効化

Mc:
  runtime identity-free、source import 0、P除去で能力消失、
  P交換で旧queue無効化、観測由来座標、決定論的compile、
  OFFLINE実level完了、既存P0-P9回帰維持

non-goals:
  game/level router、replay、固定action列、answer map、
  literal座標、source/hidden-state runtime参照、P10完了主張

evidence boundary:
  legacy codeとenvironment sourceは解析・反証だけに使用する。
  active runtimeは現在render、available action、承認済みM、Pだけを読む。

falsification:
  P-Bでもoperatorが動く、P交換後に旧queueが動く、
  固定座標を返す、失敗後も同planを再実行する、
  HDSを迂回してwrite/emitする場合はREJECT。
```

## 2. 出典

| 項目 | 値 |
|---|---|
| legacy repository | `gatchimuchio/ARC-Layer-0-Functional-Compliance` |
| inspected commit | `96f3d2deebc7c05c07e7c817f131a2a5136f5822` |
| source path | `agent/my_agent.py` |
| source blob | `d32297f2818eb354bff5e3304d9f4b657304c907` |
| inspected helper | `_ft09_frame_plan` |
| target implementation | `ARC-AGI-3-Agents/arc3_agi_agent/semantic_operators.py` |

旧helperから採用したのは、rendered relation tileを抽出し、局所制約を
GF(2)として解く純計算の考え方だけである。旧fileをimportせず、コードの
責任境界、型、状態所有者、P parameter化を新規に実装した。

## 3. 採用・不採用境界

採用:

- rendered gridだけからtile、relation、status paletteを抽出する
- click effectを局所関係として組み立てる
- binary系をGF(2)、ternary系を循環差分として解く
- camera scaleとclick centerを現在renderから再導出する
- 残planを受動Mへ直列化し、次cycleで読む

不採用:

- game IDによるrouter
- level counterによるhelper選択
- bridge用の固定click
- policy側が所有するqueue
- replay、既知action列、literal座標
- source class、hidden field、evaluator内部state

## 4. P/C/J/M分離

`p10_instruction_compiler.py`がP4 predecessorから次の3体を明示compileする。

| variant | operator | 意味 |
|---|---:|---|
| P-A | 4 | symbolic body + relation/object/rewrite/fruit instructions |
| P-B | 0 | parametric body、意味演算子除去対照 |
| hybrid | 4 | parametric body + relation/object/rewrite/fruit instructions |

palette、stride、tile size、detector/transform名、precondition、falsifierは
P bundleへ置く。CはPから渡されたinstructionがなければ計画しない。
Jだけがwrite/emitを許可し、Mはqueueと失敗署名を受動保持する。

M内queueには使用したP instruction digestを保持する。PをP-Bへ交換した、
または同名operatorのparameterが変わった場合、Cは待機中queueを無効化し、
旧P由来actionを実行しない。

## 5. 残存リスク

- このoperatorの実証範囲はrendered relation-toggle構造であり、未知構造への
  一般汎化を証明しない。
- `tile_size=3`を処理できることは現Layer-0 primitiveの能力境界である。
  値の選択はPが行うが、任意tile size対応は未実装である。
- P10全183 levelの完了条件は未成立であり、P11へ進めない。
