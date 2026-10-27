# ARC3-RUN-003 C2-037：現在観測決定的tie-break RNG ablation

## 指示・仮説

- 指示ID：`ARC3-RUN-003-C2-037`（2026-10-24 JST）。正本v3.0／`ARC3-RUN-003`。
- 対象故障は[C1-010](../../検証/運転記録/ARC3-RUN-003_C1-010_policy乱数変動優先故障選定_20261024.md)の公開探索policy seed変動。
- 仮説：全Action経路で`random.Random(None)`由来の単一run列へ依存せず、各選択時に現在公開board・合法Action集合・同一run内のAction/color集計からtie-break RNGを再初期化すると、同じ観測＋同じpolicy統計に対する選択を再現しながら、異なる公開状態ではtie-break列を更新できる。
- C2-022初期board hash seedの一度限り再利用はlevelsを失って棄却済み。今回それを再導入しない。

## 許可範囲

- `検証/`配下に隔離された評価専用policy subclass/runnerとtargeted testsを追加する。提出runtime・shared policy・Notebookを直接変更しない。
- fixed development split seed `20261022`の5環境、environment seeds `7/31/73`、各80 Action、GAME_OVER後RESET有効。現行探索policyとablationを同じ初期公開状態で対にする。
- treatmentのRNG seed materialは現在`state`・最新公開board・利用可能Action・同一runのgeneric Action/color統計と座標試行数に限る。canonical serializeしてSHA-256を計算し、先頭64bitを当該`選ぶ()`呼出の乱数種にする。`game_id`、`level_id`、filename、GUID、hash、trajectory、secret情報は入力しない。
- HDS、HDS候補、UCB係数、報酬、Action合法性、座標候補・探索集合自体は変更しない。RNG初期化だけを介入する。
- per-game run/board/action rowsを保存せず、匿名aggregateのみ記録する。

## 禁止・保持条件

- 最良policy seed、未使用holdout、game/level IDによる選択を行わない。固定Action列を再生しない。
- `接続/観測駆動探索Action.py`、`接続/ARC3提出agent.py`、HDS、candidate v4、事前記憶、Notebook/kernel、保護ファイル、文書正本を変更しない。
- Kaggle kernel upload/run、Competition Rerun、提出、score照会を行わない。
- eval outputにboard、座標、game/level ID、個別run、trajectory、特徴値を残さない。

## 試験・受入・採否

1. paired runごとの開始状態・board・available Actionsが一致すること。policy seed/path以外に条件差がないこと。
2. RNG material unit testで、ID・盤面hash・saved trajectoryが含まれず、同一materialなら同seed、統計・公開状態が変われば再計算されること。
3. Actionは毎手直前の`available_actions`内、RESET条件適合、illegal/duplicate/HOLDが0であること。
4. dev 3 seeds全てでprevious/currentのcompleted levelsが維持または増加し、currentにWIN減少・安全回帰がないこと。総delta、no-op、GAME_OVER/RESET、行動数を記録。
5. 各seedでlevel deltaが負なら即棄却。受入してもholdoutへ進む前にC3 independent policy-seed testを別taskで行う。WIN 0なら攻略成功と呼ばない。
6. evaluator/test/source/input/output SHA、previous/current/delta、採否、次工程を追記記録へ残す。
