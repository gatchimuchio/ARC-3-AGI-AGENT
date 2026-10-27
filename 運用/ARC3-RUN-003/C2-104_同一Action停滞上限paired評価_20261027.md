# ARC3-RUN-003 C2-104 — 同一Action停滞上限のpaired評価

## 判定

**棄却。** 5公開環境×3 seedの15対で平均RHAEはprevious/candidateともに `0.240596656`、差 `0`。完了level差も `0` で、候補側はAction `+13`、no-op `+10` となった。閾値介入は11回発生したがスコア改善がなく、holdoutへ進めない。

## 条件と結果

- previousは現行の観測駆動探索方針。candidateは評価専用の上限方針で、level未進行の同一合法Actionが8回続き、他の合法Actionを一度ずつ試した後に限って、次の選択から同じAction番号を除外する。
- 固定split seed `20261022`、policy/environment seeds `7/31/73`、各run最大80 action。各対は同一公開初期状態と同一seedで実行し、公式公開baselineを使う同じRHAE評価関数で採点。
- 結果: mean RHAE `0.240596656 → 0.240596656` (`Δ 0`); improved/regressed/tied `0/0/15`; completed levels `3 → 3`; wins `0 → 0`; actions `832 → 845`; no-ops `23 → 33`; GAME_OVER events `12 → 12`; cap interventions `11`.
- 同一初期状態 `15/15`、介入前action prefix一致 `15/15`、scorecard契約違反 `0`、illegal action `0`、duplicate observation `0`。
- dev gateは平均score改善 `>=0.01`、level後退なし、開始状態と介入前prefix全件一致、契約違反・illegal・duplicateなし、実介入あり。平均score条件を満たさないため候補を棄却。Notebook/runtime/HDSには反映しない。

## 公式提出の並行確認

2026-10-27 19:52:09 UTCのread-only Kaggle CLI履歴では、最新の公式submission `57688735` は `COMPLETE`、public score `28.07`、private scoreなし。説明欄は既存のlegacy visual C2-046 v13 fallback。比較元 `57577905` はpublic `23.86` で、現行最高値との差は `+4.21`。submission-limitsは `numToday=1`, `numTotal=8`。当日枠は使用済み。C2-104候補の提出・kernel push・rerunは行っていない。

## 証拠

- scorecard: [C2-104_action-streak-cap-dev.json](../証拠/ARC26-UNIFIED/C2-104_action-streak-cap-dev.json), SHA-256 `889CB7956514AC841475B38AD7DA011D35E8234118452933515CDB8071EEBA9B`
- paired evaluator SHA-256 `1A3CC77390AF7A590717BF5291B5135618F18E83B2B1430B59451105300D138C`
- local runner SHA-256 `DDCD523AF222A95EB7A3AD1AE73351B011ECCBCD25359EAA6B9C7A69792718E9`
- official history/quota snapshot: [ARC3-C2-104-official-history-quota-20261027T195209Z.json](../証拠/ARC26-UNIFIED/ARC3-C2-104-official-history-quota-20261027T195209Z.json)

Reproduce the local paired evaluation with `.venv/Scripts/python.exe 検証/ARC3C2-104_action-streak-paired-evaluation.py --stage dev`. This is local public-environment evidence and is not an official competition score.
