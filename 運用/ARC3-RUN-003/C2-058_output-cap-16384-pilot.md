# C2-058: model output-cap 16,384 private pilot

## 仮説

C2-046 slim の固定3ゲームで、247応答中1件が12,288生成トークンを全てreasoningに使い、`finish_reason=length`でtool callを返せなかった。出力上限だけを16,384へ上げれば、その局面で次のActionまで決め切る可能性がある。推論時間が伸びる可能性もあるため、得点と実行時間の両方で判定する。

## 一因子変更

C2-046 slim を基準に、cell 5 の `LOCAL_ANALYZER_MAX_OUTPUT` だけを `12*1024` から `16*1024` に変更。Notebook全25セル中の変更はcell 5のみで、他のNotebook bytesを含め差分は設定値1箇所。kernel metadataは同一でprivate/GPU有効/Internet無効。候補Notebook SHA-256 `b72c8105c1916337d6016e224762afe3d9a0c3be24a4abb539b83591e6ca48d0`、metadata SHA-256 `e31a7418a9430d0a343cac1dad9e408a3bafa64970d830d3f1be82742ed49372`。

## 事前根拠

C2-046 slim controlのmeanは19.309155943771326。request log SHA-256 `041c2aeee7dc283fd8324eff6932cea0938c63917ffa6173e706933c8c2c026f`。247応答の内訳はtool_calls 246、length 1。12,288 tokensに達したlength応答はreasoning 12,288 tokensで、model serverのcontext length 139,264 tokens内に16,384 output capは収まる。

## 採否

同一3公開開始状態・seed・制限で公式local `EnvironmentScoreCalculator` を使い、meanが19.309155943771326を超え、対応差分meanが正の場合に限り次段へ進める。per-game score、完了level、wins、action数、runtime、generated tokens、terminal state、開始状態を照合する。合格しても昇格前に公開25環境で検証し、公式評価は別ゲートとする。公式提出・quota使用はしない。

## Preflight

Kaggleの現在latestはversion 26で、remote pullのNotebook SHA-256 `5bceca28e889a3f6483224f0e6f96b8191c1c142270e7b3a0f890bd8eb908632` が保存済みversion 26と一致し、read-only statusは`KernelWorkerStatus.COMPLETE`。version 27としてprivate offline pilotを1回だけ起動する準備が完了。機械可読証拠: `運用/証拠/ARC26-UNIFIED/ARC3-C2-058-preflight-20261025T124914Z.json`。

## Kaggle private pilot start

- 2026-10-25 12:50:00 UTC: one push created kernel version 27; immediate read-only status was `KernelWorkerStatus.RUNNING`. Candidate notebook SHA-256 remains `b72c8105c1916337d6016e224762afe3d9a0c3be24a4abb539b83591e6ca48d0`; metadata SHA-256 remains `e31a7418a9430d0a343cac1dad9e408a3bafa64970d830d3f1be82742ed49372`. No official competition submission was made; quota was not queried during this action.
- Push/status evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-058-push-20261025T125000Z.json`.

## Version 27 source verification

- Read-only pull shows all 25 cell source texts match the candidate exactly. The raw notebook hashes differ because Kaggle stores the source as strings instead of lists in cells 0, 5, 13, 18, and 22. Kernel metadata differences are Kaggle-generated: `code_file` filename changed, and `enable_tpu`, `id_no`, `keywords` were added.
- Latest status observed 2026-10-25 12:51:35 UTC: `KernelWorkerStatus.RUNNING`. Exact-version log-output query returned no matching files at 12:52:46 UTC. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-058-remote-source-20261025T125316Z.json`.

## Follow-on optimization diagnostic from C2-046 control

- Across the three matched control runs, `ACTION1`–`ACTION6` produced a board change in 378/387 actions (97.67%). The same runs completed 7 levels total and had 0 wins at mean 19.309155943771326. Board changes are not equivalent to score progress; this makes a simple no-op suppression factor a weaker next target than improving progression/planning. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-058-control-diagnostic-20261025T125633Z.json`.

## Context-budget side effect

- Raising only the output reserve from 12,288 to 16,384 lowers the same 131,072-token context setting's input limit from 118,272 to 114,176 (512-token safety margin included). The control request log has one prompt at 116,437 tokens, which is 2,261 above the candidate input limit and may be pruned earlier. Thus this pilot measures the output-cap increase together with that input-history tradeoff. If warranted by the score, a follow-up can keep the old input budget by raising the configured context window to 135,168, below the server's 139,264-token limit. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-058-context-budget-risk-20261025T130557Z.json`.

## Version 27 status follow-up

- 2026-10-25 13:12:48 UTC: latest read-only kernel status remains `KernelWorkerStatus.RUNNING`; exact-version `.log` output was not available at 13:03:19 UTC. No score is available yet. No official competition submission or quota use. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-058-v27-status-20261025T131248Z.json`.

- 2026-10-25 13:27:15 UTC: latest read-only status remains `KernelWorkerStatus.RUNNING`; exact-version log output was still unavailable at 13:19:22 UTC. No score yet. No official submission or quota use. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-058-v27-status-20261025T132715Z.json`.

- 2026-10-25 13:41:56 UTC: latest read-only kernel status remains `KernelWorkerStatus.RUNNING`; exact-version log output was still unavailable at 13:37:01 UTC. No score yet. No official submission or quota use. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-058-v27-status-20261025T134156Z.json`.

- 2026-10-25 13:57:06 UTC: latest read-only status remains `KernelWorkerStatus.RUNNING`; exact-version log output was unavailable at 13:47:59 UTC. No score yet. No official submission or quota use. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-058-v27-status-20261025T135706Z.json`.


## Version 27 terminal result

- Exact kernel version 27 status was `KernelWorkerStatus.COMPLETE` at 2026-10-25T14:22:19Z. No official competition submission or submission quota use occurred. Candidate Notebook SHA256 is `b72c8105c1916337d6016e224762afe3d9a0c3be24a4abb539b83591e6ca48d0`.
- Read-only output collection preserved 23 files (111,767,942 bytes), manifest SHA256 `eccd612c2f083969536b9bf53addc5e7f7c647c607e08cdeef21c7f2a457a205`. `benchmark.json` SHA256 is `cfe7c7c70ef06c719a01011a527ee9cd6742299f60cf40f615bfaf73fdc2596b`.
- The scorecard used `arc_agi.scorecard.EnvironmentScoreCalculator`. All three game starts match the C2-046 slim control for initial state fields, level count, and public baseline action counts.

| Game | C2-046 control: score / completed / actions | C2-058 v27: score / completed / actions | Paired delta | Candidate wall time (s) |
| --- | ---: | ---: | ---: | ---: |
| `m0r0-492f87ba` | 47.619048 / 4 / 160 | 0.000000 / 0 / 160 | -47.619048 | 3060.3 |
| `sk48-d8078629` | 2.777778 / 1 / 99 | 1.698901 / 1 / 100 | -1.078877 | 1200.2 |
| `tn36-ef4dde99` | 7.530642 / 2 / 130 | 35.714286 / 4 / 160 | +28.183643 | 2057.5 |

- Matched mean: C2-046 `19.309155944` → C2-058 `12.471062097`, delta `-6.838093847`. Completed levels: 7 → 5; actions: 389 → 420; per-action generated-token history sums: 439,748 → 414,720. Wins: 0 → 0; all three candidate runs ended `gave_up`; paired games improved/unchanged/regressed = 1/0/2.
- Decision: **REJECT C2-058**. The 16,384 output cap did not pass the predeclared mean/paired-delta gate. Candidate `m0r0-492f87ba` fell from 47.619048 to 0; `tn36-ef4dde99` rose from 7.530642 to 35.714286; `sk48-d8078629` fell from 2.777778 to 1.698901.
- Output limitation: Kaggle marked `requests.jsonl` partial. Local file is 12,582,912 bytes and its sidecar reports remote size 103,567,872 bytes. This transcript is not used for the scorecard; benchmark and per-game event outputs were complete. The scorecard v1/v2 drafts are retained as history; v3 fixes their token-history extraction and is the result of record.
- Next experiment C2-059 changes only configured context window from 131,072 to 135,168 relative to C2-058, keeping 16,384 output cap and restoring the previous effective input budget. It remains a private pilot and must beat the C2-046 matched mean with positive paired delta to be accepted.
- Evidence: status/output `運用/証拠/ARC26-UNIFIED/ARC3-C2-058-v27-complete-20261025T141624Z.json` (SHA256 `18e299a251a7be51593e2dbae07e7554c8db615d36feaeab13138e207917a765`); final scorecard `運用/証拠/ARC26-UNIFIED/ARC3-C2-058-v27-terminal-scorecard-v3.json` (SHA256 `1e485df14da71fc82ce3ed2f2e7a82d92daa72b8f67497ea93e2813be52b655f`); scorecard source `運用/証拠/ARC26-UNIFIED/ARC3-C2-058-v27-scorecard.py` (SHA256 `4d72fbe3dc13b9ce0d5c2ed6d2b28216eb24bdc4b73f7c06a6fbdaf463602729`).


## Per-level failure signature (2026-10-25T14:33:02Z)

The 12.471 mean is not a uniform regression. On `m0r0-492f87ba`, C2-058 used all 160 candidate actions on level 1 and completed 0 levels, while C2-046 completed 4 levels with 160 actions total. On `sk48-d8078629`, C2-058 used 78 actions on level 1 versus 43 for control; both completed 1 level. On `tn36-ef4dde99`, C2-058 improved from 2 to 4 completed levels. This supports investigating early-level progress and context recovery, but does not prove context truncation caused the failure. The diagnostic is descriptive only and does not change the REJECT decision.

- Machine-readable per-level evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-058-v27-level-diagnostic-20261025T143302Z.json` (SHA256 `9f8e62471e56276cb25b9db9689b4ce4e055a79f82c4679b266f171611b97794`).


## Board-change diagnostic for the m0r0 regression (2026-10-25T14:48:14Z)

Counting only `type=action` events, the candidate changed the board on 402/420 actions (95.71%); C2-046 changed it on 379/389 (97.43%). In the largest loss, m0r0, 149/160 candidate actions changed the board, but it completed 0 levels versus 4 for control. This weakens a simple no-op-suppression explanation and points toward a progression/planning failure without identifying its cause. It is diagnostic only.

- Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-058-v27-board-change-diagnostic-20261025T144814Z.json` (SHA256 `2546969ffc7ce977ab895fdf5edaaef5e34d5f586bb525c64a827ffd7efc6ba5`).
