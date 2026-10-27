# ARC3-RUN-003 C2-044：現行agent候補Kaggle Phase A実行

## 目的・根拠

- 正本は `運用/ARC3-RUN-003/v3_0/` および共通3点セットv3.0。
- `ARC3-SUBMIT-011` は現行agent bundle SHA `d00ab4af0613a4949e13a886fbaf12a5b61c868c3aaaac42320ba38d1268301e` と一致し、builder tests 5件PASS、OFFLINE official Starter 25環境を実行済み。結果は4 level進行、0 win、illegal 0であり、能力改善は未成立。
- 既存private kernel `tecchannn/arc3-observation-driven-exploration-candidate` はKaggle上でCOMPLETEだが、remote notebook SHA `404bd92b146dd9fffc0375b6a52b4a914988a05374d6b9c17f1eacf6d794aa46` はローカル候補と異なる。
- 現行Kaggle公式概要はNotebook提出、CPU/GPU run time上限9時間、Internet無効を示す。公式StarterはSave & Run AllをPhase A、Submit to Competition/Competition RerunをPhase Bとして区別する。参照: `https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/overview`、`https://github.com/arcprize/ARC-AGI-3-Kaggle-Starter`。

## 許可範囲

- 新しいkernel versionとして現行 `出力/ARC3-SUBMIT-011/` を既存の同一private slugへ `kaggle kernels push` し、Kaggle Phase A (Save & Run All) を一度実行する。
- Kaggleのkernel statusと生成artifactを読み取り、Phase AがCOMPLETEか、placeholder `submission.parquet` が生成されたかを確認する。
- KaggleへCompetition Rerun/Submitを行わない。競技submission、score、日次枠は本タスクの対象外。Phase A placeholderを公式scoreや採点提出とみなさない。
- source agent/HDS、`SUBMIT-011`、過去kernel version、AGENTS.md、`制御/現在状態.json` を変更しない。kernel pushが失敗または実行中なら同一内容の再pushを避け、status/logを追跡する。
- credentialsや非公開入力・正解を出力・証拠保存しない。

## 提出前観測

- Kaggle公式履歴とquotaの最新記録は 2026-10-24T10:48:04Z。submission `57577905` はCOMPLETE/public_score 23.86だが、現行ローカルagentへの帰属なし。残枠0。
- Phase Aのみを実行するためCompetition Rerunを開始しない。もしCLI/UIが競技提出を促す／開始する曖昧な状態を示した場合は押さず、公式履歴を再照会する。

## 受入条件

1. pushed kernel metadataのslugとNotebook SHAが `SUBMIT-011` と一致する。
2. Kaggle Phase A statusがCOMPLETE、`submission.parquet` のplaceholder schema/rowを確認する。これは実scoreではない。
3. 同一日の日次競技枠が消費されず、Competition Rerun/Submitが起きていない。
4. 実行status、artifact SHA、対象Notebook SHA、取得UTC時刻、quota不変を証拠化し、append-only work ledgerへ追記する。
5. protected hashesを再確認する。失敗時は原因を記録し重複pushを避ける。
