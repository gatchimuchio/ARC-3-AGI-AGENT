# ARC3-RUN-003 C1-017：model-guided v5の公開25環境scorecard再採点

## 問い

C2-027 private kernel version 5は、同一開始状態の公開25環境でlocal v4より完了level数が増えたと記録されている。この差が、action効率と未完了levelを含む公式 `EnvironmentScoreCalculator` のgame score平均でも改善になるかを、保存artifactだけでpaired再採点する。

## 固定対象・比較

- previous：`出力/ARC3-RUN-002-local/C2-025-v4-public-25-retry.json` の探索policy、environment/policy seed 31、各環境最大80 requests。
- current：`出力/ARC3-RUN-002-local/C2-027-kaggle-output/v5/benchmark.json` のmodel-guided version 5、既存比較artifact `C2-027-comparison.json` と出力manifestを照合する。
- Kaggle公式公開環境metadataの `baseline_actions` と、固定`.venv`の `arc_agi.scorecard.EnvironmentScoreCalculator` を採点根拠にする。private benchmarkの `final_score` は同じ計算の再現性照合にのみ用い、公式Competition scoreとは呼ばない。
- 両artifactをenvironment keyでメモリ内対応させ、25/25のkey集合・初期state/board/level一致を確認する。key・board・levelごとの値やaction列は出力へ保存しない。

## 判定・保持条件

- 25環境すべてが一対一で対応し、candidate側level別action数の合計・完了数・per-game scoreがprivate benchmark記録と一致し、baseline側scorecard集計が既存C0 seed 31結果と一致すれば採点を受け入れる。
- previous/current/paired delta、score改善・同点・悪化の環境数、完了level数、総action数、WIN数、上限到達数だけを匿名集計する。
- RHAE平均が増えていればmodel-guided v5を次のC1候補として支持する。公式能力・hidden転移・競技採点の完了、C2-027候補の現在版への同一性、再提出許可とは扱わない。平均が増えない、metadata/計算不一致、対応数不足なら候補昇格せずC1へ戻る。
- Kaggle API、kernel、Notebook、policy、HDS、保護対象へ書き込まない。新しい実行・submission・Competition Rerunは行わない。

## 完了証拠

- evaluator/source/test/output/input SHA256を記録する。
- 出力からenvironment/level ID、GUID、盤面、座標、Action列、request/transcript内容が復元できないことを確認する。
