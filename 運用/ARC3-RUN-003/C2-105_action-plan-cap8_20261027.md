# C2-105 — 1回のPython呼び出し内の行動計画を8手で区切る診断

観測時刻: 2026-10-27T20:17:41Z
基準カーネル: tecchannn/arc3-model-guided-c2-025 version 29 / COMPLETE
候補Notebook SHA-256: 64C07C3C7988043533430683F9DF32C5E6776946E2FCD4578DDE0678DE5B1A1E

## 狙い

C2-104の「同じ合法Actionを連続選択した場合の制限」とは別の介入として、v28/v29の公開開始局ログでanalysis_stepあたり8手を超える行動列が観測されたため、Python snippetごとの実行Action上限を8手にする候補を作成した。8手後に最新状態をモデルへ返し、再観察・再計画を促す。ログのanalysis_stepはPython呼び出し境界と同一とは未確認である。

v28/v29の公開開始局ログをanalysis_stepごとに集計した結果:

| 基準 | analysis step数 | 8手超のstep | 8手超step内のaction数 | 8手目より後のaction数 |
|---|---:|---:|---:|---:|
| v28 | 95 | 12 | 145 | 49 |
| v29 | 106 | 15 | 180 | 60 |

これは再観察の診断根拠であり、analysis_stepをPython呼び出し境界と断定するものでも、再計画後の挙動やスコアを予測するものでもない。イベントファイルごとのSHA-256は証拠JSONに記録した。

## 候補と事前確認

- version 29 Notebook 64C07C3C7988043533430683F9DF32C5E6776946E2FCD4578DDE0678DE5B1A1Eを基に作成。Notebook cell 3だけ変更し、他のセルとkernel metadataは同一。
- python_tool_sandbox.pyのaction helperで、同一snippet内の実行済みAction数を数える。8手超の計画は残り枠までに切り詰め、実行結果と現在状態をモデルへ返した後にsnippetを停止する。
- Unified diff全hunkの行数整合を検証。変更hunkは旧行350/363、後続hunk開始位置も累積追加行数分移動した。
- cap境界の合成確認: 8手ちょうど、12手計画の先頭8手、snippet内で4手実行済みの場合の残り4手、上限到達後の拒否を確認。これは合成preflightであり、実ゲーム検証ではない。
- 候補Notebookはローカル 出力/ARC3-RUN-003-local/C2-105-action-plan-cap8/submission.ipynb。再生成スクリプト: [C2-105-build-action-plan-cap8.py](../../検証/ARC3-RUN-003/C2-105-build-action-plan-cap8.py)。

## 結果と運用状態

候補のprivate実行とスコアは NOT_MEASURED。Kaggle version 30へのpushは行っていない。最後に確認できた別候補C2-089のprivate push rejectionは2026-10-27T16:38:26ZのMaximum weekly GPU quota of 30.00 hours reached.で、reset時刻は提供されていない。新しい容量回復証拠がないため再試行していない。

公式履歴を2026-10-27T20:17:41Zに再読したところ、submission 57688735はCOMPLETE, public 28.07, private scoreなし。説明欄上は既存のlegacy visual C2-046 v13 fallbackであり、C2-105の得点ではない。比較元57577905のpublic 23.86からの差は+4.21。直近のquota証拠（2026-10-27T19:18:07Z）では当日1件使用、残り0、累計提出数8。2026-10-27T20:17:41Zの履歴にも新規提出はなく、この作業によるquota使用は0。

## 判断

C2-105は PREPARED_LOCAL_ONLY。スコア改善は未確認のため採用・昇格しない。GPU容量が回復した証拠を確認後、version 30としてprivate実行し、同一公開開始環境でv29およびC2-046 v13と比較する。公式の28.07はC2-046 v13 fallbackの結果として分離して記録する。

## 三点セット・保護対象

この作業開始時に現行v6共通3点セットとARC3 3点セットを再読し、hashを確認した。ファイルhashは証拠JSONとwork-ledgerに記録した。AGENTS.mdおよび制御/現在状態.jsonのhashも照合済みで、変更なし。

## 証拠

- Candidate build: 運用/証拠/ARC26-UNIFIED/ARC3-C2-105-action-plan-cap8-prepared-20261027T201256Z.json
- Review/trace/official snapshot: 運用/証拠/ARC26-UNIFIED/ARC3-C2-105-action-plan-cap8-review-20261027T201741Z.json
- Official raw history: 運用\証拠\ARC26-UNIFIED\ARC3-C2-105-official-history-raw-20261027T201741Z.json
- Latest official score and quota source: 運用\証拠\ARC26-UNIFIED\ARC3-C2-102-official-limits-raw-20261027T191807Z.txt

## 2026-10-27 UTC follow-up — private push rejected

The prepared private candidate was pushed once with the pinned Kaggle CLI. Kaggle returned the exact message: Kernel push error: Maximum weekly GPU quota of 30.00 hours reached. The process exit code was 0 despite that rejection message. No candidate version ID or score was returned. A read-only kaggle kernels status tecchannn/arc3-model-guided-c2-025 query returned KernelWorkerStatus.COMPLETE without a version number, so that status cannot be attributed to candidate version 30.

- Candidate Notebook SHA-256: 64c07c3c7988043533430683f9df32c5e6776946e2fcd4578dde0678de5b1a1e; metadata confirms private=true, GPU=true, internet=false.
- Private score: NOT_MEASURED; candidate execution/version creation: NOT_CONFIRMED.
- No official submission or Competition Rerun was attempted; this operation used 0 official daily submissions.
- No retry until fresh weekly GPU capacity evidence. Continue local score improvement work while capacity is unavailable.
- Push evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-105-private-push-rejection-20261027T204849Z.json.

## 2026-10-27T20:55:53Z — action-batch exposure refinement

The original motivation grouped actions by analysis_step. That is only a coarse diagnostic and does not measure the candidate's action-list exposure. A new read-only analyzer groups the v29 traces by the harness-recorded batch_index/batch_size fields instead:

| Trace | Action events | Action batches | Batches over 8 | Executed actions after 8 |
|---|---:|---:|---:|---:|
| m0r0-492f87ba | 160 | 160 | 0 | 0 |
| sk48-d8078629 | 94 | 54 | 2 | 3 |
| tn36-ef4dde99 | 135 | 67 | 3 | 8 |
| Total | 389 | 281 | 5 | 11 |

All 11 post-cap actions changed the public board; none returned nonzero reward, completed a level, or ended a game. Thus the cap would touch 5/281 logged action batches (1.8%) and 11/389 actions (2.8%) in these traces. Earlier analysis_step counts of 15/106 and 60 tail actions are not the cap's measured batch exposure. Whether earlier re-observation changes the next plan or score remains unknown.

Decision: keep C2-105 unscored and unpromoted, and deprioritize it versus changes that cover a larger share of observed failures. Do not push again until fresh weekly GPU capacity evidence. This analysis does not establish a score effect.

The first analyzer invocation stopped on its own batch-start validation (Invalid action batch sequence in m0r0-492f87ba_p0_events.jsonl: index=1, size=1). The start check was corrected; the metrics above come only from the successful rerun over unchanged trace files. Ruff passed.

- Analyzer: [C2-105-action-batch-exposure.py](../../検証/ARC3-RUN-003/C2-105-action-batch-exposure.py), SHA-256 `cd6ed70875a644b8a8cd0667e7fe4f5ca8786cc5a800e06e137869446c1c1a19`.
- Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-105-action-batch-exposure-20261027T205525Z.json`, SHA-256 `ba55d6ec9a30a662c4f2e09311615b4f0f778d4c760276af08fb706d6888ac2a`.
