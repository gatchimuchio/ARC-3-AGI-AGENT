# ARC3-RUN-003 C1-018：model-guided v5 公式Competition Rerun

## 判定対象と根拠

- C1-017 paired scorecardのcandidateはC2-027 private kernel version 5。公開25環境でprevious `0.2275316149`、current `11.5232172832`、delta `+11.2956856683`、22改善/2同点/1後退、完了level `3→47`。WINは`0→0`、candidate 25 runすべて`gave_up`、4 runは1200秒上限。したがって公式Rerunを試す根拠にはなるが、公式改善・勝利・hidden転移の証明ではない。
- 保存source `出力/ARC3-RUN-002-local/C2-029-source/v5-submission.ipynb` SHA256 `5763f69d0794d7161dbe81a967edd2c10a6810c92ed1a28208bd47222fd5dfbc` は、C2-027 version 5に記録されたhashと一致。
- notebook metadata: competition source `arc-prize-2026-arc-agi-3`、GPU有効、Internet無効、RTX PRO 6000。attached model instance IDs `1007514` / `1007009` はKaggle Models APIで取得でき、双方のmodel card/licenseはQwen Community License 1.0。データsourceは `dfranzen/pennyroyal-v253` と `dfranzen/taaf-kaggle-source-bundle-copy`（Kaggle datasets listingで公開sourceとして確認）。
- competition modeは `KAGGLE_IS_COMPETITION_RERUN` を検出してlive gatewayから環境一覧を読み、`bm.games = _competition_games()`へ進む。offline環境限定・1200秒/80 Action guardとplaceholder `submission.parquet`生成は非competition分岐のみ。competition設定は1 pass、concurrency 120、per-game cap 532分（8時間52分）。Kaggle公式要件はNotebook提出、Internet無効、GPU run 9時間以下、submission file自動生成。
- ARC Prize公式RHAEはlevel completionとhuman baseline比のaction効率を測る。したがってローカルRHAEの改善は勝利数だけでは判定しないが、公式hidden scoreへ転用もしない：[ARC-AGI-3 Scoring Methodology](https://github.com/arcprize/docs/blob/main/methodology.mdx)。
- Kaggle一次情報：[competition overview/requirements](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/overview)、[Qwen3.8 model license](https://huggingface.co/Qwen/Qwen3.8-Flash-Next/blob/main/LICENSE)。モデル名・ライセンス名は保存Notebook metadataとKaggle Models APIのread-only結果にも一致。

## 提出操作と確認

- 提出直前のread-only履歴：`57541830 COMPLETE / public 0.25`、`57527856 COMPLETE / public 0.00`。提出枠は `Submissions today: 0 / Lifetime submissions: 5 / Remaining today: 1`。
- 初回CLI試行は出力名 `-f` を省略し、Kaggle API `CreateCodeSubmission` がHTTP 400を返した。続けて履歴と提出枠をread-only再確認し、提出ID・枠消費とも変化なしを確認。CLI実装の引数契約を確認してから、正しいNotebook生成物名 `submission.parquet` を付けて実行した。
- 正式操作：`.venv\Scripts\kaggle.exe competitions submit -f submission.parquet -k tecchannn/arc3-model-guided-c2-025 -v 5 -m "ARC3-RUN-003 C1-018 paired public scorecard validated v5" arc-prize-2026-arc-agi-3`。
- Kaggle提出履歴から新規ID `57577905` を取得。受付時刻 `2026-10-24 01:15:49.963 UTC`、file `submission.parquet`、Notebook `tecchannn/arc3-model-guided-c2-025` version `5`、状態 `PENDING`、public/private score未記録。
- 提出後のquota read-only値：本日1件、累計6件、残り0件。追加提出・再送・別version Rerunは行わない。
- Kaggle `kernels status` は最新kernel versionの `KernelWorkerStatus.ERROR` を返す。提出は明示的にversion 5を指定し、v5の過去private runはC2-027で`COMPLETE`・出力取得済み。latest versionの状態を提出ID `57577905` の状態へ転用しない。
- 2026-10-24 01:18:37 UTC、Codex local thread heartbeat `arc3-submission-57577905-status-check` を15分間隔で作成。履歴・枠のread-only確認だけを行い、状態不変時は通知せず、終端状態で停止する。再提出は指示対象外。

## 未完了と再開点

公式scoreは未取得で、今回の終了条件はまだ満たしていない。15分後を目安に、以後30〜60分間隔で同一IDの履歴状態をread-only再照会する。`PENDING`の解消目的で同一版を再提出しない。公式スコア数値・取得時刻が出たら同じ記録へ追記し、B1 `0.25`およびB0 `0.00`との差を固定する。

```powershell
.\.venv\Scripts\kaggle.exe competitions submissions -c arc-prize-2026-arc-agi-3 --csv
.\.venv\Scripts\kaggle.exe competitions submission-limits -c arc-prize-2026-arc-agi-3
```

## 2026-10-24 01:24 UTC read-only follow-up

- Kaggle competition submission historyを再照会。`57577905`は引き続き`SubmissionStatus.PENDING`で、public/private scoreは未提供。`57541830 COMPLETE/public 0.25`、`57527856 COMPLETE/public 0.00`も既記録どおり。
- 同分の`submission-limits`は本日1件、累計6件、残り0件。再提出・Rerunなし。次回も同じIDだけを照会する。

## 2026-10-24 01:33 UTC read-only follow-up

- Kaggle history: `57577905 PENDING`、public/private score未提供。既存B1 `57541830 COMPLETE/public 0.25`、B0 `57527856 COMPLETE/public 0.00`も変化なし。
- `submission-limits`: 本日1件、累計6件、残り0件。追加提出・Rerunなし。

## 2026-10-24 01:43 UTC read-only follow-up

- Kaggle history: `57577905 PENDING`、public/private score未提供。既存B1 `57541830 COMPLETE/public 0.25`、B0 `57527856 COMPLETE/public 0.00`に変化なし。
- `submission-limits`: 本日1件、累計6件、残り0件。追加提出・Rerunなし。同一IDを次回もread-only照会する。

## 2026-10-24 01:45 UTC read-only follow-up

- Kaggle history: `57577905 PENDING`、public/private score未提供。B1 `57541830 COMPLETE/public 0.25`、B0 `57527856 COMPLETE/public 0.00`に変化なし。
- `submission-limits`: 本日1件、累計6件、残り0件。追加提出・Rerunなし。heartbeatは`ACTIVE`で、同一IDの次回照会を継続する。

## 2026-10-24 01:46 UTC read-only kernel-log diagnosis

- `.venv\Scripts\kaggle.exe kernels status tecchannn/arc3-model-guided-c2-025/5` は`KernelWorkerStatus.ERROR`。同versionの`kernels logs`には`taaf.kaggle: TRUE_SUBMISSION=False`、SGLang readiness deadline `1800s`、`DEADLINE ... server inference readiness was not confirmed`、`offline benchmark not started`の後にRuntimeErrorが記録されていた。
- これはNotebook v5の非competition実行ログであり、公式competition rerun環境ではない。したがって提出`57577905`の終端失敗原因とは認定しない。提出履歴は同時点で引き続き`PENDING`、score空欄。Kaggle history/limits APIの読取自体は成功し、quotaは本日1件・累計6件・残り0。
- 既存のC2-027保存public outputの完了記録と、この別runの失敗ログを混同しない。Notebook変更・再実行・再提出なし。公式提出IDだけを引き続きread-only追跡する。

## 2026-10-24 02:01 UTC read-only follow-up

- Kaggle history: 57577905 PENDING、public/private score未提供。既存B1 57541830 COMPLETE/public 0.25、B0 57527856 COMPLETE/public 0.00に変化なし。
- submission-limitsは同時点で本日1件、累計6件、残り0件。heartbeatはACTIVE、追加提出・Rerunなし。同一IDを次回もread-only照会する。

## 2026-10-24 02:16 UTC read-only follow-up

- Kaggle submission history再照会: `57577905 PENDING`、public/private score未提供。B1 `57541830 COMPLETE/public 0.25`、B0 `57527856 COMPLETE/public 0.00`は変化なし。
- `submission-limits`: 本日1件、累計6件、残り0件。再提出・Rerunなし。Codex heartbeat `arc3-submission-57577905-status-check` は `ACTIVE`。
- 次回も同一IDをread-only照会する。公式スコア未取得のためC1-018は未完了。

## 2026-10-24 03:30 UTC read-only follow-up

- Kaggle submission history: `57577905` remains `SubmissionStatus.PENDING`; official `publicScore` and `privateScore` are empty. No terminal result yet.
- `submission-limits`: `numToday=1`, `numTotal=6`, remaining quota `0`. This matches the 03:15 UTC observation.
- History and limits only were read. No submission, rerun, push, or Notebook/kernel edit. Continue the same-ID read-only monitor.
## 2026-10-24 03:45 UTC read-only follow-up

- Kaggle submission history: `57577905` remains `SubmissionStatus.PENDING`; official `publicScore` and `privateScore` are empty. No terminal result yet.
- `submission-limits`: `numToday=1`, `numTotal=6`, remaining quota `0`. This matches the 03:30 UTC observation.
- History and limits only were read. No submission, rerun, push, or Notebook/kernel edit. Continue the same-ID read-only monitor.


## 2026-10-24 04:00 UTC read-only follow-up

- Kaggle submission history: `57577905` remains `SubmissionStatus.PENDING`; official `publicScore` and `privateScore` are empty. No terminal result yet.
- `submission-limits`: `numToday=1`, `numTotal=6`, remaining quota `0`. This matches the 03:45 UTC observation.
- History and limits only were read. No submission, rerun, push, or Notebook/kernel edit. Continue the same-ID read-only monitor.


## 2026-10-24 04:02:13 UTC read-only follow-up

- 保存済みのKaggle履歴証拠 運用/証拠/ARC26-UNIFIED/official-history-20261024T040213Z.json は、Kaggle SDK competition_submissions による read-only 取得。57577905 は PENDING、public/private score は空欄。これはCLIによる新規照会ではない。
- quota はこの証拠では再取得されていない。最終確認は04:00 UTCで、本日1件・累計6件・残り0件。マニフェストでもquota観測時刻を04:00 UTCと区別した。
- 予定の04:15 UTCに、設定済み .venv Kaggle CLIで同一IDの履歴と submission limits のみを再確認する。提出、Rerun、push、Notebook/kernel変更なし。


## 2026-10-24 04:15:21 UTC read-only follow-up

- 設定済み .venv Kaggle CLI の提出履歴で 57577905 は SubmissionStatus.PENDING。publicScore/privateScore は空欄。B1 57541830（COMPLETE/public 0.25）およびB0 57527856（COMPLETE/public 0.00）との比較対象に変化なし。
- submission-limits は本日1件、累計6件、残り0件。履歴・limits のread-only照会のみを実施し、提出、Rerun、push、Notebook/kernel変更なし。
- 詳細な正規化済みCLI観測: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T041521Z.json。次回予定は 2026-10-24T04:30Z UTC。


## 2026-10-24 04:30:21 UTC read-only follow-up

- 設定済み .venv Kaggle CLIの提出履歴で 57577905 は SubmissionStatus.PENDING。publicScore/privateScore は空欄。B1 57541830（COMPLETE/public 0.25）およびB0 57527856（COMPLETE/public 0.00）との比較基準に変化なし。
- submission-limits は本日1件、累計6件、残り0件。履歴・limitsのread-only照会のみで、提出、Rerun、push、Notebook/kernel変更なし。
- 正規化済みCLI観測: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T043021Z.json。次回予定は 2026-10-24T04:45Z UTC。


## 2026-10-24 04:45:21 UTC read-only follow-up

- 設定済み .venv Kaggle CLIの提出履歴で 57577905 は SubmissionStatus.PENDING。publicScore/privateScore は空欄。B1 57541830（COMPLETE/public 0.25）およびB0 57527856（COMPLETE/public 0.00）との比較基準に変化なし。
- submission-limits は本日1件、累計6件、残り0件。履歴・limitsのread-only照会のみで、提出、Rerun、push、Notebook/kernel変更なし。
- 正規化済みCLI観測: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T044521Z.json。次回予定は 2026-10-24T05:00Z UTC。


## 2026-10-24 05:00:19 UTC read-only follow-up

- 設定済み .venv Kaggle CLIの提出履歴で 57577905 は SubmissionStatus.PENDING。publicScore/privateScore は空欄。B1 57541830（COMPLETE/public 0.25）およびB0 57527856（COMPLETE/public 0.00）との比較基準に変化なし。
- submission-limits は本日1件、累計6件、残り0件。履歴・limitsのread-only照会のみで、提出、Rerun、push、Notebook/kernel変更なし。
- 正規化済みCLI観測: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T050019Z.json。次回予定は 2026-10-24T05:15Z UTC。


## 2026-10-24 05:15:25 UTC read-only follow-up

- 設定済み .venv Kaggle CLIの提出履歴で 57577905 は SubmissionStatus.PENDING。publicScore/privateScore は空欄。B1 57541830（COMPLETE/public 0.25）およびB0 57527856（COMPLETE/public 0.00）との比較基準に変化なし。
- submission-limits は本日1件、累計6件、残り0件。履歴・limitsのread-only照会のみで、提出、Rerun、push、Notebook/kernel変更なし。
- 正規化済みCLI観測: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T051525Z.json。次回予定は 2026-10-24T05:30Z UTC。


## 2026-10-24 05:30:15 UTC read-only follow-up

- 設定済み .venv Kaggle CLIの提出履歴で 57577905 は SubmissionStatus.PENDING。publicScore/privateScore は空欄。B1 57541830（COMPLETE/public 0.25）およびB0 57527856（COMPLETE/public 0.00）との比較基準に変化なし。
- submission-limits は本日1件、累計6件、残り0件。履歴・limitsのread-only照会のみで、提出、Rerun、push、Notebook/kernel変更なし。
- 正規化済みCLI観測: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T053015Z.json。次回予定は 2026-10-24T05:45Z UTC。


## 2026-10-24 05:45:20 UTC read-only follow-up

- 設定済み .venv Kaggle CLIの提出履歴で 57577905 は SubmissionStatus.PENDING。publicScore/privateScore は空欄。B1 57541830（COMPLETE/public 0.25）およびB0 57527856（COMPLETE/public 0.00）との比較基準に変化なし。
- submission-limits は本日1件、累計6件、残り0件。履歴・limitsのread-only照会のみで、提出、Rerun、push、Notebook/kernel変更なし。
- 正規化済みCLI観測: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T054520Z.json。次回予定は 2026-10-24T06:00Z UTC。


## 2026-10-24 06:00:29 UTC read-only follow-up

- 設定済み .venv Kaggle CLIの提出履歴で 57577905 は SubmissionStatus.PENDING。publicScore/privateScore は空欄。B1 57541830（COMPLETE/public 0.25）およびB0 57527856（COMPLETE/public 0.00）との比較基準に変化なし。
- submission-limits は本日1件、累計6件、残り0件。履歴・limitsのread-only照会のみで、提出、Rerun、push、Notebook/kernel変更なし。
- 正規化済みCLI観測: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T060029Z.json。次回予定は 2026-10-24T06:15Z UTC。


## 2026-10-24 06:15:18 UTC read-only follow-up

- 設定済み .venv Kaggle CLIの提出履歴で 57577905 は SubmissionStatus.PENDING。publicScore/privateScore は空欄。B1 57541830（COMPLETE/public 0.25）およびB0 57527856（COMPLETE/public 0.00）との比較基準に変化なし。
- submission-limits は本日1件、累計6件、残り0件。履歴・limitsのread-only照会のみで、提出、Rerun、push、Notebook/kernel変更なし。
- 正規化済みCLI観測: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T061518Z.json。次回予定は 2026-10-24T06:30Z UTC。


## 2026-10-24 06:30:18 UTC read-only follow-up

- 設定済み .venv Kaggle CLIの提出履歴で 57577905 は SubmissionStatus.PENDING。publicScore/privateScore は空欄。B1 57541830（COMPLETE/public 0.25）およびB0 57527856（COMPLETE/public 0.00）との比較基準に変化なし。
- submission-limits は本日1件、累計6件、残り0件。履歴・limitsのread-only照会のみで、提出、Rerun、push、Notebook/kernel変更なし。
- 正規化済みCLI観測: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T063018Z.json。次回予定は 2026-10-24T06:45Z UTC。


## 2026-10-24 06:45:16 UTC read-only follow-up

- 設定済み .venv Kaggle CLIの提出履歴で 57577905 は SubmissionStatus.PENDING。publicScore/privateScore は空欄。B1 57541830（COMPLETE/public 0.25）およびB0 57527856（COMPLETE/public 0.00）との比較基準に変化なし。
- submission-limits は本日1件、累計6件、残り0件。履歴・limitsのread-only照会のみで、提出、Rerun、push、Notebook/kernel変更なし。
- 正規化済みCLI観測: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T064516Z.json。次回予定は 2026-10-24T07:00Z UTC。


## 2026-10-24 06:45:49 UTC read-only follow-up

- Configured local .venv Kaggle CLI: submission 57577905 remains SubmissionStatus.PENDING; publicScore/privateScore are blank. Baselines 57541830 (COMPLETE/public 0.25) and 57527856 (COMPLETE/public 0.00) are unchanged.
- submission-limits: 1 today, 6 lifetime, 0 remaining. Read-only history and quota queries only; no submit, Rerun, push, or Notebook/kernel edits.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T064549Z.json. Numeric score remains unavailable; follow the same ID again at 2026-10-24T07:00:49Z.


## 2026-10-24 07:01:25 UTC read-only follow-up

- Configured local .venv Kaggle CLI: submission 57577905 remains SubmissionStatus.PENDING; publicScore/privateScore are blank. B1 57541830 (COMPLETE/public 0.25) and B0 57527856 (COMPLETE/public 0.00) are unchanged.
- submission-limits: 1 today, 6 lifetime, 0 remaining. Read-only history and quota queries only; no submit, Rerun, push, or Notebook/kernel edits.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T070125Z.json. Numeric score remains unavailable; follow the same ID again at 2026-10-24T07:16:25Z.


## 2026-10-24 07:02:12 UTC：07:00の追加読取と定期記録の整合

- 07:00:20 UTCに設定済み .venv Kaggle CLIで行ったread-only history/limits確認は、定期予定07:00:49 UTCより29秒早い追加読取だった。statusはPENDING、public/private score空欄、quotaは1件/6件/残り0で、直後の定期観測07:01:25 UTCと一致。
- 07:01:25 UTCの定期観測は既にC1-018報告、運転台帳、score-ledgerへ記録済み。manifestをその観測へ同期し、07:00:20のJSONは補足観測として関連付けた。早い観測を後からscore-ledger末尾へ逆順追加していない。
- 次回はscore-ledgerに記録された07:16:25 UTC。これまで追加提出・Rerun・push・Notebook/kernel変更なし。


## 2026-10-24 07:16:58 UTC read-only follow-up

- Configured local .venv Kaggle CLI: submission 57577905 remains SubmissionStatus.PENDING; publicScore/privateScore are blank. B1 57541830 (COMPLETE/public 0.25) and B0 57527856 (COMPLETE/public 0.00) are unchanged.
- submission-limits: 1 today, 6 lifetime, 0 remaining. Read-only history and quota queries only; no submit, Rerun, push, or Notebook/kernel edits.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T071658Z.json. Numeric score remains unavailable; follow the same ID again at 2026-10-24T07:31:58Z.


## 2026-10-24 07:32:28 UTC read-only follow-up

- Configured local .venv Kaggle CLI: submission 57577905 remains SubmissionStatus.PENDING; publicScore/privateScore are blank. B1 57541830 (COMPLETE/public 0.25) and B0 57527856 (COMPLETE/public 0.00) are unchanged.
- submission-limits: 1 today, 6 lifetime, 0 remaining. Read-only history and quota queries only; no submit, Rerun, push, or Notebook/kernel edits.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T073228Z.json. Numeric score remains unavailable; follow the same ID again at 2026-10-24T07:47:28Z.


## 2026-10-24 07:47:52 UTC read-only follow-up

- Configured local .venv Kaggle CLI: submission 57577905 remains SubmissionStatus.PENDING; official publicScore/privateScore are blank. B1 57541830 (COMPLETE/public 0.25) and B0 57527856 (COMPLETE/public 0.00) are unchanged.
- submission-limits: 1 today, 6 lifetime, 0 remaining. Read-only history and quota queries only; no submit, Rerun, push, or Notebook/kernel edits.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T074752Z.json. The recorded next check is 2026-10-24T08:47:52Z UTC.

## 2026-10-24 08:48:47 UTC read-only follow-up

- Configured local .venv Kaggle CLI: submission 57577905 remains SubmissionStatus.PENDING; official publicScore/privateScore are blank. B1 57541830 (COMPLETE/public 0.25) and B0 57527856 (COMPLETE/public 0.00) are unchanged.
- submission-limits: 1 today, 6 lifetime, 0 remaining. Read-only history and quota queries only; no submit, Rerun, push, or Notebook/kernel edits.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T084847Z.json. The recorded next check is 2026-10-24T09:48:47Z UTC.

## 2026-10-24 08:49:12 UTC supplemental read-only confirmation

- A due-time read at 08:48:08 UTC returned the same PENDING row, blank public/private scores, and quota; the command wrapper did not retain the history command exit code. The complete confirmation at 08:49:12 UTC returned exit code 0 for both read-only CLI commands and matched the scheduled 08:48:47 UTC observation.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T084912Z.json. No submission, Rerun, push, or Notebook/kernel edits.

## 2026-10-24 09:32:48 UTC read-only history follow-up

- Configured local .venv Kaggle CLI history: submission 57577905 remains SubmissionStatus.PENDING; publicScore/privateScore are blank. B1 57541830 (COMPLETE/public 0.25) and B0 57527856 (COMPLETE/public 0.00) are unchanged. No numeric score is observed.
- This history response did not include submission limits. The latest quota at that time remained the 08:48:47 UTC read: 1 today, 6 lifetime, 0 remaining.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T093248Z.json. The same submission was due again at 2026-10-24T09:48:47Z UTC. No submission, Rerun, push, or Notebook/kernel edit.

## 2026-10-24 09:48:57 UTC read-only history follow-up

- Configured local .venv Kaggle CLI history: submission 57577905 remains SubmissionStatus.PENDING; official publicScore/privateScore are blank. B1 57541830 (COMPLETE/public 0.25) and B0 57527856 (COMPLETE/public 0.00) are unchanged.
- This history response did not include submission limits. At the next read 09:49:11 UTC, submission-limits returned 1 today, 6 lifetime, 0 remaining.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T094857Z.json. The next scheduled check is 2026-10-24T10:48:47Z UTC.

## 2026-10-24 09:49:11 UTC supplemental read-only quota confirmation

- Both configured local .venv Kaggle CLI queries exited 0. History matched the 09:48:57 UTC PENDING result with blank public/private scores; submission-limits confirmed 1 today, 6 lifetime, 0 remaining.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T094911Z.json. No submission, Rerun, push, or Notebook/kernel edit.

## 2026-10-24T09:55:30Z official CLI history and quota follow-up

- Read-only history confirms submission 57577905 remains PENDING with blank public/private scores. Previous completed public score 0.25 (57541830) is unchanged.
- Submission limits: 1 today, 6 lifetime, 0 remaining. No submit, rerun, push, or Notebook/kernel edit.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T095530Z.json. Scheduled next query remains 2026-10-24T10:48:47Z UTC.


## 2026-10-24 10:07 UTC 追記・訂正：Kaggle kernel version selector監査

先行記録の『`kernels status .../5` と同versionのログ』という表現はversion 5を指す根拠にならない。ARC3 `.venv` のKaggle CLI 2.2.4 API実装（`kaggle_api_extended.py` SHA-256 `210e589ab1f7359ffb560aacfe1c003ac1bc844c366f4ff709bf3d13de4d5458`）では、`kernels_status` と `kernels_output` はversion suffixをparseするものの、API requestへownerとkernel slugだけを渡し、versionを送らない。今回の出力ログに付けた`/5`指定もeffectiveではない。

取得したmain/serveログのSHA-256はそれぞれ`6588c4c2a985b31dd7a4d09868e3d66be9882a21cb0406d3852338e1569eef4c` / `46ca97a7cfe418394c89074cb231a0c8dcd441b07ac1a9bf1c7df8e15cabaded`で、既存C2-035のprivate v10 controlログと完全一致する。ログ内は`TRUE_SUBMISSION=False`、1800秒readiness deadline、offline benchmark未開始。よって確認対象は既知のprivate v10失敗であり、57577905/version5の公式Competition Rerun失敗を示さない。`wrapt`の例外は観測されたが因果関係は未確定。元のraw logは保持し、この訂正を優先する。

提出57577905は最後の公式観測（2026-10-24 09:55:30 UTC）で引き続きPENDING、公式score未観測、当日残枠0。次回公式履歴照会は10:48:47 UTCのまま。今回、履歴再照会・rerun・提出はしていない。機械可読監査: `運用/証拠/ARC26-UNIFIED/ARC3-kernel-version-selector-audit-20261024T100750Z.json`。

## 2026-10-24 10:48:04 UTC terminal official result

- Configured local .venv Kaggle CLI history: submission 57577905 is SubmissionStatus.COMPLETE with official publicScore 23.86. privateScore is blank/not provided.
- Comparison: B1 57541830 public 0.25, delta +23.61; B0 57527856 public 0.00, delta +23.86.
- submission-limits: 1 today, 6 lifetime, 0 remaining. Both read-only commands exited 0. No submission, Rerun, push, or Notebook/kernel edit was performed.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T104804Z.json. This result is terminal; recurring status check is being stopped.
## 2026-10-24T10:58:02Z scheduled read-only Kaggle observation

- Submission 57577905: SubmissionStatus.COMPLETE, public score 23.86.
- Limits: today=1, lifetime=6, remaining=0. No submit, rerun, push, or Notebook edit was performed.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T105802Z.json. Next scheduled query: 2026-10-25T10:58:02Z UTC.

## 2026-10-24T17:39:23Z scheduled read-only Kaggle observation

- Submission 57577905: SubmissionStatus.COMPLETE, public score 23.86.
- Limits: today=1, lifetime=6, remaining=0. No submit, rerun, push, or Notebook edit was performed.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T173923Z.json. Next scheduled query: 2026-10-25T17:39:23Z UTC.


## 2026-10-24 17:55:41 UTC read-only follow-up

- Kaggle history: submission 57577905 remains `COMPLETE`, publicScore 23.86; privateScore not provided. No newer ARC3 submission is listed.
- Submission limits: 1 today, 6 lifetime, 0 remaining today. Both CLI reads were read-only; no submission, rerun, push, or Notebook/kernel edit was performed.

## 2026-10-24T21:21:37Z scheduled read-only Kaggle observation

- Submission 57577905: SubmissionStatus.COMPLETE, public score 23.86.
- Limits: today=1, lifetime=6, remaining=0. No submit, rerun, push, or Notebook edit was performed.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T212137Z.json. Next scheduled query: 2026-10-25T21:21:37Z UTC.

## 2026-10-24T22:45:22Z scheduled read-only Kaggle observation

- Submission 57577905: SubmissionStatus.COMPLETE, public score 23.86.
- Limits: today=1, lifetime=6, remaining=0. No submit, rerun, push, or Notebook edit was performed.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T224522Z.json. Next scheduled query: 2026-10-25T22:45:22Z UTC.

## 2026-10-24T23:00:54Z scheduled read-only Kaggle observation

- Submission 57577905: SubmissionStatus.COMPLETE, public score 23.86.
- Limits: today=1, lifetime=6, remaining=0. No submit, rerun, push, or Notebook edit was performed.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261024T230054Z.json. Next scheduled query: 2026-10-25T23:00:54Z UTC.

## 2026-10-25T00:45:00Z scheduled read-only Kaggle observation

- Submission 57577905: SubmissionStatus.COMPLETE, public score 23.86.
- Limits: today=0, lifetime=6, remaining=1. No submit, rerun, push, or Notebook edit was performed.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261025T004500Z.json. Next scheduled query: 2026-10-26T00:45:00Z UTC.

## 2026-10-25T01:16:45Z scheduled read-only Kaggle observation

- Submission 57612586: SubmissionStatus.PENDING, public score unobserved.
- Limits: today=1, lifetime=7, remaining=0. No submit, rerun, push, or Notebook edit was performed.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261025T011645Z.json. Next scheduled query: 2026-10-25T01:21:45Z UTC.

## 2026-10-25T01:23:12Z scheduled read-only Kaggle observation

- Submission 57612586: SubmissionStatus.PENDING, public score unobserved.
- Limits: today=1, lifetime=7, remaining=0. No submit, rerun, push, or Notebook edit was performed.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261025T012312Z.json. Next scheduled query: 2026-10-25T01:38:12Z UTC.

## 2026-10-25T01:38:20Z scheduled read-only Kaggle observation

- Submission 57612586: SubmissionStatus.PENDING, public score unobserved.
- Limits: today=1, lifetime=7, remaining=0. No submit, rerun, push, or Notebook edit was performed.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261025T013820Z.json. Next scheduled query: 2026-10-25T02:08:20Z UTC.

## 2026-10-25T03:36:53Z scheduled read-only Kaggle observation

- Submission 57612586: SubmissionStatus.COMPLETE, public score 0.03.
- Limits: today=1, lifetime=7, remaining=0. No submit, rerun, push, or Notebook edit was performed.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261025T033653Z.json. Next scheduled query: 2026-10-26T03:36:53Z UTC.

## 2026-10-25T04:52:21Z scheduled read-only Kaggle observation

- Submission 57612586: SubmissionStatus.COMPLETE, public score 0.03.
- Limits: today=1, lifetime=7, remaining=0. No submit, rerun, push, or Notebook edit was performed.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261025T045221Z.json. Next scheduled query: 2026-10-26T04:52:21Z UTC.

## 2026-10-25T05:09:32Z scheduled read-only Kaggle observation

- Submission 57612586: SubmissionStatus.COMPLETE, public score 0.03.
- Limits: today=1, lifetime=7, remaining=0. No submit, rerun, push, or Notebook edit was performed.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261025T050932Z.json. Next scheduled query: 2026-10-26T05:09:32Z UTC.

## 2026-10-25T05:14:36Z scheduled read-only Kaggle observation

- Submission 57612586: SubmissionStatus.COMPLETE, public score 0.03.
- Limits: today=1, lifetime=7, remaining=0. No submit, rerun, push, or Notebook edit was performed.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261025T051436Z.json. Next scheduled query: 2026-10-26T05:14:36Z UTC.

## 2026-10-25T05:18:28Z scheduled read-only Kaggle observation

- Submission 57612586: SubmissionStatus.COMPLETE, public score 0.03.
- Limits: today=1, lifetime=7, remaining=0. No submit, rerun, push, or Notebook edit was performed.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261025T051828Z.json. Next scheduled query: 2026-10-26T05:18:28Z UTC.

## 2026-10-25T05:20:50Z scheduled read-only Kaggle observation

- Submission 57612586: SubmissionStatus.COMPLETE, public score 0.03.
- Limits: today=1, lifetime=7, remaining=0. No submit, rerun, push, or Notebook edit was performed.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261025T052050Z.json. Next scheduled query: 2026-10-26T05:20:50Z UTC.

## 2026-10-25T05:26:43Z scheduled read-only Kaggle observation

- Submission 57612586: SubmissionStatus.COMPLETE, public score 0.03.
- Limits: today=1, lifetime=7, remaining=0. No submit, rerun, push, or Notebook edit was performed.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261025T052643Z.json. Next scheduled query: 2026-10-26T05:26:43Z UTC.

## 2026-10-25T05:27:42Z scheduled read-only Kaggle observation

- Submission 57612586: SubmissionStatus.COMPLETE, public score 0.03.
- Limits: today=1, lifetime=7, remaining=0. No submit, rerun, push, or Notebook edit was performed.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261025T052742Z.json. Next scheduled query: 2026-10-26T05:27:42Z UTC.

## 2026-10-25T05:46:47Z scheduled read-only Kaggle observation

- Submission 57612586: SubmissionStatus.COMPLETE, public score 0.03.
- Limits: today=1, lifetime=7, remaining=0. No submit, rerun, push, or Notebook edit was performed.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261025T054647Z.json. Next scheduled query: 2026-10-26T05:46:47Z UTC.

## 2026-10-25T11:46:16Z scheduled read-only Kaggle observation

- Submission 57612586: SubmissionStatus.COMPLETE, public score 0.03.
- Limits: today=1, lifetime=7, remaining=0. No submit, rerun, push, or Notebook edit was performed.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261025T114616Z.json. Next scheduled query: 2026-10-26T11:46:16Z UTC.

## 2026-10-25T11:52:16Z scheduled read-only Kaggle observation

- Submission 57612586: SubmissionStatus.COMPLETE, public score 0.03.
- Limits: today=1, lifetime=7, remaining=0. No submit, rerun, push, or Notebook edit was performed.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261025T115216Z.json. Next scheduled query: 2026-10-26T11:52:16Z UTC.

## 2026-10-26T16:48:03Z scheduled read-only Kaggle observation

- Submission 57612586: SubmissionStatus.COMPLETE, public score 0.03.
- Limits: today=0, lifetime=7, remaining=1. No submit, rerun, push, or Notebook edit was performed.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261026T164803Z.json. Next scheduled query: 2026-10-27T16:48:03Z UTC.

## 2026-10-26T17:38:02Z scheduled read-only Kaggle observation

- Submission 57612586: SubmissionStatus.COMPLETE, public score 0.03.
- Limits: today=0, lifetime=7, remaining=1. No submit, rerun, push, or Notebook edit was performed.
- Evidence: 運用/証拠/ARC26-UNIFIED/official-cli-observation-20261026T173802Z.json. Next scheduled query: 2026-10-27T17:38:02Z UTC.


## 2026-10-27T06:03:40Z terminal status confirmation

- Submission 57577905 is `SubmissionStatus.COMPLETE`, public score 23.86, private score not provided. Delta is +23.61 versus B1 0.25 and +23.86 versus B0 0.00. C1-018 follow-up is terminal.
- The history also shows newer submission 57688735 still `PENDING`; this does not change the C1-018 result. Latest separate raw quota observation is 2026-10-27T04:32:59.503936Z (`numToday=1`, `numTotal=8`); no quota used by this read.
- Read-only evidence: `運用/証拠/ARC26-UNIFIED/official-cli-history-observation-20261027T060340Z.json`. The app automation id `arc3-submission-57577905-status-check` was not found, so no active app automation remained to disable.
