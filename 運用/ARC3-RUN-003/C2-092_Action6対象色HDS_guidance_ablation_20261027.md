# C2-092 Action6対象色HDS guidance ablation

- 状態: **15組評価中（3/15組）**。これは途中経過であり、採否・能力改善は未確定。
- 条件: 同一公開開始状態・seed 7・最大80 action、baseline と候補を同一組で対比較。候補は公開Action6対象色をHDSへ渡し、適合する既観測ルールを既存UCBのbounded pseudo-observationとして使う。ゲームID分岐・hidden情報・固定操作列なし。
- 変更境界: 検証runnerのみ。実行中も含め、HDS/runtime/agent/Notebookは変更していない。公式提出・Rerunなし。

## 測定経緯

- v1 pilotはepisode checkpointを書いた後、summary生成時に`KeyError: target_color_rule_predictions`で終了。さらにrule抽出条件がAction番号との併存を要求していたため、Action6 update内で有効な対象色ruleを0件と誤判定。失敗record `運用/証拠/ARC26-UNIFIED/ARC3-C2-092-target-color-guidance-pilot-v1-failure-20261027.json` SHA-256 `f520da357c313ff071ddb76e427bb20a041ff12f0a173881ac126bca71c01545`。v1 scorecardは無効な測定試行として保存し、採否に使わない。
- v2で抽出条件を直したpilotではbaseline/candidateともRHAE 0.0。479回照会、449回prediction use、対象色誘導70回。1組のみなのでゲート判定には使わない。
- v3で同じquery結果を局所cache化。baseline/candidate結果はv2と同じ0.0で、29回の実照会+426 cache hits、449 prediction use、70 guided choices。1組pilotでは改善も悪化もなし。

## 15組評価の進捗（2026-10-27T06:36:24Z）

| 指標 | baseline | candidate | 差分 |
|---|---:|---:|---:|
| RHAE平均（3組・途中） | 0.396825 | 0.396825 | 0.000000 |
| 改善 / 同点 / 悪化 | — | — | 0 / 3 / 0組 |
| HDS update秒合計（参考・3組） | 92.287 | 174.479 | +82.192秒 |

- 各組: baseline `[0.0, 1.1904761904761905, 0.0]`、candidate `[0.0, 1.1904761904761905, 0.0]`。途中3組では全部同点。
- 色ルール予測の実利用は継続しているが、スコア改善は未観測。候補側HDS update時間は途中測定で長く、15組完了後に同条件で負荷も確認する。
- 完了時の主チェックポイント: `運用/証拠/ARC26-UNIFIED/ARC3-C2-092-target-color-guidance-dev-20261027.jsonl`。この時点の不変snapshot: `運用/証拠/ARC26-UNIFIED/ARC3-C2-092-target-color-guidance-dev-progress-3pairs-20261027T063624Z.jsonl` SHA-256 `8ae9414cb29a466a2607ac2a30eb56c7177a88068e2c89f93be2643d3b5ddfa5`。評価はsession `86393`で継続。
- Runner: `検証/ARC3HDSAction6TargetColorGuidance.py` SHA-256 `df97bd0fb4a2bb0c2910101d36a0f8dffb11450e4f8263227ee5b9ce8c0f1c0d`。Ruffとpy_compileは事前にPASS済み。

## 公式状態と次の操作

- 既存submission 57688735は2026-10-27T06:34:58.191Z時点で`PENDING`、score欄空。旧C2-046 v13 fallbackであり、このC2-092候補ではない。別提出・quota使用なし。
- 既存submission 57577905は`COMPLETE 23.86`（private未提供）。これは既存Notebook版の公式値で、C2-092とは紐付かない。
- 次: session `86393`を監視し、残り12組の同条件比較を完了。全15組の差・費用・再現性を基に採否を決める。


## 15組評価の進捗更新（2026-10-27T06:42:13Z）

- 5/15組完了。baseline/candidateの累積RHAEは`1.190476190` / `1.190476190`、平均は`0.238095238` / `0.238095238`。5組すべて同点で、改善0・悪化0。
- HDS update秒合計はbaseline `167.471` / candidate `245.515`。色照会 `106`、cache hit `1167`、prediction use `1247`、guided choices `179`。
- 不変snapshot `運用/証拠/ARC26-UNIFIED/ARC3-C2-092-target-color-guidance-dev-progress-5pairs-20261027T064213Z.jsonl` SHA-256 `9f420ca5d00dcb3ed5b9d9e717dcafd55a7c18f02373f9ec13a56c6c180dd145`。live checkpointは引き続き更新中。


## 15組評価の進捗更新（2026-10-27T06:57:49Z）

- 10/15組完了。baseline/candidate累積RHAEは`1.925413022` / `1.925413022`、平均は`0.192541302` / `0.192541302`。10組すべて同点、改善0・悪化0。
- seed別累積点（baseline/candidate）: `{"7":{"baseline":1.1904761904761905,"candidate":1.1904761904761905,"pairs":5},"31":{"baseline":0.7349368318756073,"candidate":0.7349368318756073,"pairs":5}}`。
- HDS update秒合計はbaseline `304.015` / candidate `464.271`。対象色照会 `210`、cache hit `2291`、prediction use `2447`、guided choices `353`。
- 不変snapshot `運用/証拠/ARC26-UNIFIED/ARC3-C2-092-target-color-guidance-dev-progress-10pairs-20261027T065749Z.jsonl` SHA-256 `9333d13317c23315b543e2618af78028f7ca6b02d832bf0eec209d1547398990`。live checkpointと残り5組評価は継続中。


## 最終判定 — 2026-10-27T07:17:44Z

- **15/15組完了**。同じ15組・seed・最大80手の比較で、baseline RHAE `0.240596656`、candidate `0.240596656`、差 `0.000000000`。改善0、同点15、悪化0。level/win/no-op差は全て0。
- **dev gate不通過**（必要平均差≥0.01、実測差0）。対象色候補は採用せず、HDS/runtime/agent/Notebookへ昇格しない。公式提出・Rerunなし。
- HDS色ruleは実際にprediction use `3234`回、guided choice `460`回使われ、誘導後の結果は`{"盤面変化":460}`。それでも進行点は変わらず、学習効果は未実証。
- HDS update秒合計はbaseline `465.936` / candidate `702.112`（差`+236.176`秒、候補側`50.7%`増）。全評価elapsed `2870.081`秒。
- seed別: `[{"seed":7,"pairs":5,"baseline_mean":0.23809523809523808,"candidate_mean":0.23809523809523808,"delta_mean":0.0,"improvements":0,"ties":5,"regressions":0},{"seed":31,"pairs":5,"baseline_mean":0.14698736637512147,"candidate_mean":0.14698736637512147,"delta_mean":0.0,"improvements":0,"ties":5,"regressions":0},{"seed":73,"pairs":5,"baseline_mean":0.3367073637343908,"candidate_mean":0.3367073637343908,"delta_mean":0.0,"improvements":0,"ties":5,"regressions":0}]`。
- 完全scorecard `運用/証拠/ARC26-UNIFIED/ARC3-C2-092-target-color-guidance-dev-20261027.json` SHA-256 `2f94e9b90c03c7a446eb519035262c5e370784fdff01eaa9aa15b23e157cdfdf`、15組checkpoint `運用/証拠/ARC26-UNIFIED/ARC3-C2-092-target-color-guidance-dev-20261027.jsonl` SHA-256 `ab41e74edbbbe986f7b6c2de2bd36e96e34ed3f35be47fb92525faeb9159dd4c`。runner SHA-256 `df97bd0fb4a2bb0c2910101d36a0f8dffb11450e4f8263227ee5b9ce8c0f1c0d`、HDS SHA-256 `eaed97760656afc40088ad7e0d85a02fbd59a0d0034054956e9ead63319fba57`、prior memory manifest SHA-256 `d1b6e0cc3d14ce7c40c26567fefa226a2975c2e6d02725fb8bb404833963a1bd`、environment manifest SHA-256 `0311d965528bae4e0f58c53ea3f77d2d3c59caa47c5b00588eaa15ce1c058e80`。
- 判定原因: 色別にboard-change/no-opを予測し行動を変えたが、score改善が15組で一度もなかった。追加HDS queryは費用を増やすため、この機構は棄却。
