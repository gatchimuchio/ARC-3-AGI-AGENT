# C2-026 汎用モデル候補の公開3環境action一致比較

## 目的

C2-025でKaggle上のモデル・GPU・ARC runtime・Action/observation経路は起動したが、1公開環境でscore 0.00、完了level 0だった。25環境の長時間評価へ進む前に、公開環境一覧順の先頭3件を使い、現行ローカルv4と同じ最大80 Actionで探索進行を比べる。

これは候補選別の開発試験であり、能力改善や公式scoreを主張するものではない。ゲームIDはNotebookの公開環境一覧順に従い、評価終了後に現行v4を同じID・同じ公開開始状態で照合する。IDを方策へ渡したり、ID・filename・hashでActionや回答を分けたりしない。

## 事前証拠

- 現行公式候補は`tecchannn/arc3-observation-driven-exploration-candidate` version 4。最新公式Competition Rerun `57541830`はCOMPLETE、public `0.25`。baseline `57527856`はpublic `0.00`、private scoreは未取得。
- 汎用モデル候補は別private kernel `tecchannn/arc3-model-guided-c2-025`。C2-025 v3は`sk48-d8078629`のpublic gameで84 Action event、0/8 level、score 0.00。v4のlocal baseline JSONには同IDの80 Action、0 levelがあるが、その`same_public_start`はlocal random/exploration間の比較なのでv3との開始盤一致を示さない。両者の実行時間・評価器も異なり、採否には追加比較が必要。
- 25環境を1200秒ずつ逐次評価する上限は8時間20分に初回server cold-loadを加える。最大9時間のKaggle枠へ接近するため、先に3環境だけ確認する。

## 変更許可

- `接続/ARC3モデル推論候補/submission.ipynb`のoffline-only guard内に限り、`ARC3_DEV_GAME_LIMIT`のdefaultを1から3へ変更し、`bm.solver.max_actions_per_game=80`を設定する。
- offline-only条件の`n_passes=1`、`concurrency=1`、per-game wall-clock上限1200秒、GPU `NvidiaRtxPro6000`、Internet無効、pinned Python 3.12 Docker imageを保持する。
- competition-rerun path、モデル・prompt、action policy、HDS、観測駆動v4、`AGENTS.md`、`制御/現在状態.json`、正本ポインタには触れない。
- private kernelの通常実行のみ。Competition Rerun、新規提出、Kaggle submission quotaの消費は禁止。

## 比較条件と計測

- candidate: Notebook順の先頭3 public environments、各1 pass、同じ公開開始状態、最大80 Action eventまたは1200秒で停止。Action event数には初期RESETが含まれるかを出力で確認する。
- baseline: 既存の`public_local_environment_action_response` evaluator、現行v4、各80 Action、`retry_game_over=true`、seed31。IDを照合して対象を抽出し、candidateのinitial board/state/levelとbaseline initial board/state/levelを比較する。既存JSONの`same_public_start`はbaseline内部の2方策間に限る。保存boardがない場合、対象IDだけを同条件で再評価してinitial boardを保持する。
- 各環境について、初期・最終状態、level完了数、WIN、Action数、合法性、no-op、GAME_OVER、実時間、model tokens、同一開始状態フラグを記録する。
- Kaggle kernelがCOMPLETEしてもNotebookの`submission.parquet`を公式scoreと扱わない。private kernelの実行履歴とCompetition submission historyを別々に確認する。

## 採否条件

- static validation、GPU・private・Internet無効、pinned input、offline guard、ID-free policyを確認する。
- 同じ3公開開始状態・最大80 Actionで、candidateがbaselineより総level完了数を増やした場合、またはcandidateが1ゲームでもWINした場合に限り、別指示書を作って25環境pilotを検討する。これを超えても公式候補への昇格はしない。
- 同数以下、開始状態不一致、非法Action、runtime/error、またはhidden/evaluator依存があれば25環境評価へ進めない。失敗署名と次の優先課題を記録し、他のC工程へ移る。

## 終了条件

3環境すべてのcandidate/baseline結果、previous/current/delta、ログと主要hash、採否、次の指示書が保存されていること。競技への提出・採点は未実施のままとする。

## 実行状況

- 2026-10-23 13:59 UTC頃、offline guardを変更したprivate kernel version 4をpush。初回確認は`KernelWorkerStatus.RUNNING`、その後14:47 UTCまでにCOMPLETEを確認した。
- 完了後にNotebook outputから実際に選ばれた先頭3 IDを確認し、その公開開始状態に対するv4 baselineと照合する。実行・公式提出履歴は区別して記録する。

## 実行結果・採否

- Kaggle kernel `tecchannn/arc3-model-guided-c2-025` version 4は2026-10-23 14:11:58–14:47:23 UTCに通常private runとしてCOMPLETE。3環境、各80 Action、1 pass。Competition Rerunではない。
- 出力順は`sk48-d8078629`、`tn36-ef4dde99`、`m0r0-492f87ba`。既存baselineの`same_public_start`はlocal evaluator内のrandom/exploration方策間の開始盤一致を表し、Kaggle candidateとの一致ではなかった。
- 同一開始状態・各80 Actionでの完了level数：

| 公開環境 | local v4 baseline | model candidate v4 | 差分 |
| --- | ---: | ---: | ---: |
| `sk48-d8078629` | 0/8 | 0/8 | 0 |
| `tn36-ef4dde99` | 1/7 | 2/7 | +1 |
| `m0r0-492f87ba` | 0/6 | 1/6 | +1 |
| 合計 | 1 | 3 | +2 |

- candidateは3環境すべて80 Action eventを出し、全件`gave_up`、WIN 0。`level_completed` eventは計3、`game_over` eventは0。boardが変化しなかったAction eventは`sk48`で5、`m0r0`で2、`tn36`で0。illegal/invalid actionを示すserve.log行は0件。
- candidate summaryのmean scoreは5.16、total generated tokensは249,875、kernel経過時間は35分25秒。これはprivate kernelの開発計測であり、公式scoreではない。
- previous/current/delta：完了level `1 / 3 / +2`。採否ゲートを満たすため、C2-027の25環境pilotへ進める。公式候補への昇格は保留。
- cross-run開始盤面は後続監査で直接検証した。local evaluatorの出力から開始盤面を落とす行だけを一時コピーで外し、25環境を各1 Actionで再実行した`C2-026-start-check.json`（SHA256 `92ff190669e873bca9db8e9957337fecfac75b8260f1899f9186757186ebc90e`）から3 IDのbaseline exploration開始盤面を取得。candidate v4のinitial eventとboard/state/levelが3/3一致。
- 開始盤面SHA256（baseline=candidate）: `sk48-d8078629` `e4bbd31c5eaa4d7b7639cb3467234f506ef19f6221b357062f7f70a79936c8f2`; `tn36-ef4dde99` `3e8702e648bb97558ba2787491f62222b7148b397a9176f60c3ce18d38a62f8b`; `m0r0-492f87ba` `bb1341069e852a7c58ff55efadf07481d91af3c13f11fd3d2e791b9c061074c9`。
- `benchmark.json` SHA256 `3527f3251a6cd00b2c5179ed874241630652bfda200c0cfcb530ee43fb9e0281`、`summary.txt` `08ecedc676b354523257b39d30e38fecd3b35434128d327471ac4fa06e7a7e3f`、`serve.log` `0ca4c7a171da80088ba48d093cad2075857db1120517f9b3f663dc5e00ec645d`。
- Action event JSONL SHA256: `m0r0-492f87ba` `a8132b042cd4ff51887653274e43c011e55244840b81f65f9b35a59ec48cdc64`; `sk48-d8078629` `f034fc96f82bc78e2b2610b5dc860e15a1fc19ae55885679ddbf86d0a36f8d0e`; `tn36-ef4dde99` `2db7d12bfcab9cabccc264e58bf9df14f2d9afbe2391b0d78dcd7ca2327813cd`。
- Kaggle submission history確認済み：最新公式Competition Rerunは`57541830` COMPLETE/public `0.25`、baseline `57527856` COMPLETE/public `0.00`。この作業で新規公式提出はしていない。
- 出力保存先：`出力/ARC3-RUN-002-local/C2-025-kaggle-output/v4/`。比較元JSONは`出力/ARC3-RUN-002-local/C2-025-v4-public-25-retry.json`。
