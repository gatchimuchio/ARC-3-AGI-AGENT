# P10 rendered symbolic-rewrite 演算子移植監査

- classification: `ADAPT`
- target phase: `P10_COMPLETE_ARC3_SAMPLE_SOLVING`
- active runtime import from legacy repo: `none`
- HDS judgment: `PASS` for this operator / `HOLD` for P10

## 1. 境界

runtime入力はcurrent rendered grid、available action、versioned P instruction、
HDS承認済みpassive Mだけである。game/task/level ID、level counter、source、
hidden state、既知action列、literal座標を受け取らない。

Pはsymbol tile、connector、selector、cycle、rewrite depthの有界条件を
保持する。Cはrenderからbordered tile、rewrite row、source/output row、
active selectorを再検出する。Jは一手だけを採否し、Mは観測済みselector
cycleとconstraint解を受動保持する。

## 2. 出典と不採用境界

| 項目 | 値 |
|---|---|
| legacy repository | `gatchimuchio/ARC-Layer-0-Functional-Compliance` |
| inspected commit | `96f3d2deebc7c05c07e7c817f131a2a5136f5822` |
| source path | `agent/my_agent.py` |
| source blob | `d32297f2818eb354bff5e3304d9f4b657304c907` |
| inspected range | `_tr87_*` parser / rewrite / selector helpers |
| target implementation | `ARC-AGI-3-Agents/arc3_agi_agent/symbolic_rewrite.py` |

採用したのは、rendered symbolを回転同値で正規化し、可視connectorを
rewrite relationとして読む考え方である。旧実装のlevel引数、level別phase、
既知selector template、固定action planは不採用とした。

## 3. 現runtimeの能力

fixed-rule surfaceは可視rewriteをdepth上限まで適用し、current outputとの差を
一手ずつ縮める。editable-rule surfaceは各visible selector nodeのcycleを
実際に観測して元状態へ戻し、depth 1または2のconstraintを解いて必要offsetを
実行する。候補数、出力長、cycle長はPで有界化される。

stateは完全に直列化され、P instruction digestが変われば旧state由来の実行を
許さない。進捗後はlevel identityを参照せずresetする。

## 4. 実測

OFFLINE、seed 0、action budget 512、hybrid `p10-hybrid-v5`、
visual operator `arc3-p10-visual-operator-v12`で、対象6 levelを308 actionsで
完了した。error、GAME_OVER recovery、search reset、max-action停止はいずれも
0で、Mが次判断へ影響したcycleは284である。

この証拠は当該rendered rewrite mechanismの6 levelだけを支持する。
全183 level、未知構造への汎化、P11 release stateは支持しない。
