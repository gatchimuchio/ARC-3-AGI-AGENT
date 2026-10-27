# ARC3-RUN-003 C2-046: off control 実行記録

- 観測時刻: evidence JSONの `observed_at_utc` を参照
- 実験: `運用/ARC3-RUN-003/C2-046_level-memoryとcheckpoint-loader最適化pilot.md`
- Kaggle kernel: `tecchannn/arc3-model-guided-c2-025`, version 11, `KernelWorkerStatus.COMPLETE`
- 条件: private/GPU有効/Internet無効、`ARC3_MEMORY_SECTIONS=off`、loader `enable_multithread_load=true,num_threads=8`
- local notebook SHA-256: `b5a77e0e01906c52fd706ff31b3f73473fdf62f8e719af3d54747f3d90fbd828`
- Kaggle取得notebook SHA-256: `e218cfd6a0f253be1c4a997cbb1405323bf48747f353d8f4acd6e90ec6ca550b`
- local/remote code-cell SHA-256一致: `a190152ec35db614a359a6cf182951ba3bfe994a94c3cf3cbbf83ff5cc09da66`

## 起動と実行

`/health_generate` のHTTP 200をserver起動後1,675秒で確認し、1,800秒deadline内にbenchmarkへ進んだ。公開offline 3-game benchmarkは2026-10-24 13:21:57 UTCに開始し、14:16:13 UTCに3件すべてが160 action予算まで完了した。全件statusは`gave_up`（action予算到達）で、WINは0。private GPU runtimeの観測であり、公式Competition Rerunや提出ではない。

## 結果

- 完了level: 6 / 21
- action: 480、うちno-op 6
- GAME_OVER event: 1、WIN: 0
- generated tokens: 468,142
- benchmark elapsed: 54分15秒、各game wallclock合計: 6,547.7秒
- timeout/illegal flag: benchmark出力に明示されたflagは0件。全gameが160 action予算に到達
- 各gameの初期 `board/state/level` SHA-256（匿名・評価専用）: `3bec3c27479753759053d24afdae6f2c5457ee3d745e0e8962c58b4d3f7a9669`, `447bf976859ab60334d35c903e22948f01ee1cdbef38b92f09abd35b020ac4d2`, `f06b9984ad65b166cef59cccbd019dbc3e7e9879b6961080325b9272c042bf6a`
- output: 31 files / 149,581,685 bytes、manifest SHA-256 `dcf552aa7d6ace9dd1f5ce0944394a8d8c1d10761ca126bde8fa2636263f7c2a`
- 集計証拠SHA-256: `e2a105201aa3f72e2a180a59b896fef0884410596de03207c48261f08411ef04`

初期状態ハッシュは次の`slim`条件との公開開始状態照合専用で、solverへ渡していない。timeout/illegalを示す専用flagはrunner outputにないため、0件は「明示的な報告なし」を意味する。各gameはWINせずaction上限まで進んだ。

## 次の処置

controlは起動・benchmark完了条件を満たした。保存済みoutputと初期状態指紋を保持したうえで、同一Notebook・同一seed/予算の`slim` treatmentを1回だけ実行する。control結果だけからlevel-memoryの採用や公式能力改善を主張しない。公式候補・Competition Rerun・日次提出枠には変更なし。

## 根拠

- 集計証拠: `運用/証拠/ARC26-UNIFIED/ARC3-C2-046-off-control-20261024T141613Z.json`
- Kaggle output: `出力/ARC3-RUN-003-local/C2-046/kaggle-output/off/`
- prepared pair manifest: `出力/ARC3-RUN-003-local/C2-046/candidate-manifest.json`
