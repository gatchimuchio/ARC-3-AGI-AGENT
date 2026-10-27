# ARC3-RUN-003 C2-044 実行記録：現行agent候補Kaggle Phase A

- 正本: 共通3点セットv3.0、ARC3-RUN-003 v3.0。
- 公式規則の現行確認: Kaggle overviewではNotebook提出、Internet無効、CPU/GPU実行上限各9時間。Entry Deadline 2026-10-26、Final Submission Deadline 2026-11-02（各日23:59 UTC）。公式Starter READMEはSave & Run AllをPhase A、Competition RerunをPhase Bとして区別。
- 参照: https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/overview 、 https://github.com/arcprize/ARC-AGI-3-Kaggle-Starter

## 実行結果

- 実行時刻: 2026-10-24 11:44 UTC頃。Kaggle CLI: project `.venv`。
- `kaggle kernels push -p 出力/ARC3-SUBMIT-011` 成功。返却version: 5。Kaggle `kernels status` は `KernelWorkerStatus.COMPLETE`。
- Kaggle最新kernel pullのcell-source digest `263ccaeda6435573295deb444db01934da7e5ad26f3f81e4784eeaf552a43c2e` はローカル候補と一致。ローカルNotebook SHA `bb34b2a0b6d04e84d2a27cacb44db623233d2e367a800b2ab59e0a0383ca8e80`。Kaggle側Notebookのbytes SHAは実行後metadata差により `d9f6ac6b36f3fbfa535c8a8906bef10982aefba11c9b51cc8fef634a486e92db`。privacy、GPU/Internet無効、competition sourceなどの主要metadataは一致。
- Phase A生成物 `submission.parquet`: 1 row、列 `row_id/game_id/end_of_game/score`、型 string/string/bool/int64。記載値はNotebook所定のdummy placeholder。SHA256 `688e716e8f9ad967f6211a3796070b69c74a5adb5ce93e9f1c0ba77701ea3194`。scoreやagent勝利を示す値ではない。
- 実行ログでは35 source files検証、HDS import、placeholder作成、「no competition score was evaluated」を確認。Runtime/agent勝利能力の主張はしない。
- Phase A後にKaggle公式履歴を再照会。最新は既存 `57577905 COMPLETE/publicScore 23.86` のまま、新しいcompetition submission refなし。`23.86` は現行候補に帰属しない。quotaは10:48:04Zの最終観測で残り0、本タスク後のhistoryに提出追加なし。
- Competition Rerun/Submitは行わず、公式scoreは未取得。現行candidateのローカルStarter 25環境では0 winsのまま。
- version suffix `/5` 指定のpull APIは403だったが、current slug pullは成功し、cell-sourceが候補と一致した。kernel statusとoutputも正常。credential-pattern scanに対象パターンhitなし。
- `AGENTS.md` SHA256 `dff057d8f6ac88c688ec1d950640dc88b706d5ed9184119deda226d0109a8d42`、`制御/現在状態.json` SHA256 `0e4b29319d727896e244fe32f9726f0933f63fe007f59480272e76d46508c93c`。いずれも変更なし。

## 採否・次の処置

- Phase AのKaggle runtime wiringはPASS。official score、競技提出、agent能力は未成立。
- 次の競技提出前にUTC日付・最新rules/timeline・submission history/status/score/quota・候補SHA・Phase A完了・提出形式を当日に再確認する。同日枠はすでに使用済みの記録のため、新しいCompetition Rerunは行っていない。

Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-044-phaseA-20261024T114447Z.json` SHA256 `1006c6aece2e8510e768047b6be920504e84904dcdf58b721b2021b191d57bd7`。
Official history evidence: `運用/証拠/ARC26-UNIFIED/official-history-ARC3-phaseA-20261024T1144Z.json` SHA256 `450387fc490ea5f122185153198cc12e2ad3c3801bccdb034e5d5c7b417eeb98`。
