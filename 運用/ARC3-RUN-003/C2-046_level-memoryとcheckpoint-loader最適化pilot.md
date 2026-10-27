# C2-046: checkpoint loader optimization + level-memory pilot

## 目的

C1-019でv5のlevel遷移率がdepthとともに低下した（depth 1: 22/25、depth 2: 14/22、depth 3: 7/14、depth 4: 3/7、depth 5: 1/3）。v5では`ARC3_MEMORY_SECTIONS=off`であり、短いWorld model/Planをlevel間に保持する`slim`設定がこの劣化を緩和するか、同じ公開環境・seed・予算で比較する。

C2-034/035は推論ready前に終了し、記憶条件は未実行だった。C2-035の1800秒deadlineを延長せず、model loaderだけを並列化した新controlを用意する。controlがreadyし、benchmarkを開始・完了できた場合だけ、同一Notebook・同一条件で`slim` treatmentを1回実行する。

## 変更・比較条件

- 起点: C2-035 prepared `off` / `slim` notebooks。元のv5 source、公式提出版、HDS、`AGENTS.md`、`制御/現在状態.json`は変更しない。
- 両armの共通変更: SGLang `--model-loader-extra-config`を`enable_multithread_load=false`から`enable_multithread_load=true,num_threads=8`へ変更。checkpoint prefetch、model、draft model、server argsその他は維持。
- Control: `ARC3_MEMORY_SECTIONS=off`。Treatment: `ARC3_MEMORY_SECTIONS=slim`。
- 両armともprivate/GPU有効/Internet無効、startup deadline 1800秒、公開offline game limit 3、seed 0、1 pass、逐次実行、160 Action/game、1200秒/game。
- treatmentはcontrolが推論ready・benchmark開始を満たすまでpushしない。起動readinessが不成立なら同一条件を再試行せず終了する。

## 根拠とリスク

- 1800秒のreadiness期限で35/38 shardsに止まったC2-035を基準にする。C2-046は期限を増やさない。
- SGLang loaderは`enable_multithread_load`と`num_threads`を受け取る。checkpoint prefetch併用時はI/O oversubscriptionを避けるためmultithreadが自動無効化される場合があり、明示的に有効化する変更が読み込み短縮につながるかは未確認。公開したSGLang loader documentation/code: https://github.com/sgl-project/sglang/blob/main/python/sglang/srt/model_loader/loader.py
- multithread loadingがI/O競合で遅くなる可能性もある。readinessとbenchmark開始時刻を記録し、1800秒でfail closedする。

## 採否条件

1. controlが`/health_generate` HTTP 200の後にbenchmarkを開始し、対象3件を完了すること。
2. treatmentでもready・benchmark開始し、memory updateと後続promptへの再注入を確認すること。
3. 3件全ての初期公開board/state/levelがarm間で一致すること。
4. level完了、WIN、Action数、no-op、GAME_OVER、runtime、generated tokens、timeoutsをoff previous / slim current / deltaで記録すること。
5. 採用候補条件: level deltaが正、WIN件数が非減、memory update/reinjection成立、開始状態一致、illegal Actionなし。
6. このprivate pilotは公式scoreや能力改善を確定しない。Competition Rerun、公式提出、quota消費、push先の公式submission candidate変更を行わない。

## 出力

Notebook/source hashes、kernel version/status、startup ready time、benchmark output hashes、開始状態照合、off/slim差分と採否を実行記録へ追記する。Candidate manifest: `出力/ARC3-RUN-003-local/C2-046/candidate-manifest.json`。

## Cross-level scope clarification

- The prepared slim arm inherits `ARC3_WM_WIPE_ON_LEVEL=1`; the source clears stored memory at each level transition. C2-046 therefore evaluates within-level memory and loader feasibility, not persistent knowledge transfer between levels. C2-048 isolates retain-and-revise as a follow-up.
