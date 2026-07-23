# P10 rendered object-target制御 演算子移植監査

- classification: `ADAPT`
- target phase: `P10_COMPLETE_ARC3_SAMPLE_SOLVING`
- active runtime import from legacy repo: `none`
- HDS judgment: `PASS` for this operator / `HOLD` for P10

## 1. 境界

runtime入力はcurrent rendered grid、available action、versioned P instruction、
HDS承認済みpassive Mだけである。game/task/level ID、level counter、source、
hidden state、既知route、literal座標を受け取らない。

Pは四隅target、compact control、状態から除外するinterface色、探索上限、
座標降下条件、dense mechanism model条件を保持する。Cは現在renderから
controlとgoalの対応を再検出し、Jが一手だけ採否する。Mは観測済み遷移、
hazard、座標降下phase、学習済みpermutation候補を受動保持する。

## 2. 出典と不採用境界

| 項目 | 値 |
|---|---|
| legacy repository | `gatchimuchio/ARC-Layer-0-Functional-Compliance` |
| inspected commit | `96f3d2deebc7c05c07e7c817f131a2a5136f5822` |
| source path | `agent/my_agent.py` |
| source blob | `d32297f2818eb354bff5e3304d9f4b657304c907` |
| inspected range | `_lp85_*_frame_control`, `_lp85_*_frame_plan` |
| target implementation | `ARC-AGI-3-Agents/arc3_agi_agent/semantic_operators.py` |

採用したのは、rendered componentからtarget/control関係を抽出し、作用を
再観測して更新する考え方だけである。旧実装のlevel分岐、個別frame plan、
固定click列、既知配置の座標条件は不採用とした。

## 3. 現runtimeの能力

単純な一方向controlは現在goal displacementから一手を導出する。作用対応が
不明なsurfaceは、観測済み遷移graph、bounded coordinate descent、
permutation候補学習の順に扱う。dense surfaceでは観測した作用だけから
Hungarian assignmentでmechanism対応を構成し、次cycleで再検証する。

同一P instruction digestでないqueueは無効化される。進捗後はlevel identityを
参照せずplanner stateを初期化する。失敗actionはhazardとして保持され、
同じ状態での次判断から除外される。

## 4. 実測

OFFLINE、seed 0、action budget 256、P-A
`p10-p-a-symbolic-v4`で、対象8 levelを235 actionsで完了した。
error、GAME_OVER recovery、search reset、max-action停止はいずれも0で、
Mが次判断へ影響したcycleは188である。

この証拠は当該rendered mechanismの8 levelだけを支持する。全183 level、
未知構造への汎化、P11 release stateは支持しない。
