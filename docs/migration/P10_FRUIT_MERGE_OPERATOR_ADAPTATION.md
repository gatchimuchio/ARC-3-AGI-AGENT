# P10 rendered fruit-merge / actor制御 演算子監査

- classification: `REBUILD`
- target phase: `P10_COMPLETE_ARC3_SAMPLE_SOLVING`
- active runtime import from legacy repo: `none`
- HDS judgment: `PASS` for bounded integration / `HOLD` for operator acceptance and P10

## 1. 境界

runtime入力はcurrent rendered grid、available action、versioned P instruction、
HDS承認済みpassive Mだけである。game/task/level ID、level counter、source、
hidden state、replay、固定route、answer map、literal座標表を受け取らない。

Pはrendered glyph、actor mask、target範囲、click lattice、移動量、探索上限を
保持する。Cはcurrent renderから要求rank/actor、fruit/actor、targetを毎cycle
再検出し、一手だけの候補を生成する。JだけがemitとM更新を承認し、Mは
surface signature、観測済み失敗click、直前action種別を受動保持する。

## 2. 実装

`arc3_agi_agent/fruit_merge.py`は次を実装する。

- compact interface glyphから要求rank/actorを読む
- playfieldのsame-rank fruit、actor、irregular targetを再検出する
- 要求targetへのroute、same-rank接近、merge、actor回避を候補化する
- action後にsurfaceが消失した場合、undo候補を一度だけ発行する
- 失敗clickを最大64件のversioned passive stateへ保持し再選択から除外する
- P instruction digestまたはrendered surface構造が変われば状態を初期化する

`SampleFrameProjection`は同一frameのlayer、signature、action surface、
terminal stateを一度だけmaterializeし、runtimeとemissionで共有する。
hidden mutable cacheは持たず、projectionはimmutableである。

## 3. 不採用境界

旧資産やdiagnostic replayから、game/level router、既知action列、固定click、
source state、hidden evaluator fieldはactive runtimeへ移していない。
診断時に得た個別座標やaction列はP bundle、C selector、M payloadへ保存しない。

## 4. 実測と判定

OFFLINE、seed 0、hybrid `p10-hybrid-v5`、visual operator
`arc3-p10-visual-operator-v12`、action budget 160のSU15 runで4 / 9 levelを
完了した。errorは0、HDS recoveryは1、search resetは0、M影響cycleは154で
ある。level 5は`MAX_ACTION_STOP`であり、全9 level完了、max-action停止0、
同一条件の完全再現という採用条件を満たさない。

したがって、この差分はidentity-free bounded operatorと失敗保持経路の
統合証拠であり、SU15攻略済み、汎化済み、P10完了の証拠ではない。
