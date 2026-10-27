# C2-029 80 Action打切りと勝利未達のhorizon検査

## 目的

C2-027では25件中21件が80 Action上限に達し、25件すべてが`gave_up`、WIN 0だった。一方、同一公開開始状態で47 levelを完了しlocal v4より+44だった。現在の80 Action horizonが部分進捗を勝利へつなぐ機会を打ち切っているか、同じmodel/prompt/policyで最初の3環境だけ160 Actionまで延ばすprivate試験を一度行う。

## 比較対象

- Candidate: `tecchannn/arc3-model-guided-c2-025` version 5の先頭3公開環境`sk48-d8078629`, `tn36-ef4dde99`, `m0r0-492f87ba`。
- Previous: version 5とそのbaselineの同一3開始盤面。version 5は候補の確率性・実行揺らぎを含む既存観測であり、単純なpaired continuationとみなさない。
- 現行notebookはoffline guardの評価件数default 25、max Action 80。実施時はoffline-onlyで件数を3、max Actionを160へ変える。model、prompt、solver policy、runtime 1,200秒、逐次1 pass、analyzer timeout 180秒、Kaggle private/GPU/Internet無効を維持する。

## 禁止・保持条件

- `TRUE_SUBMISSION`のCompetition path、model/prompt/solver、HDS、公式入力、AGENTS.md、制御/現在状態.json、文書正本ポインタを変更しない。
- game IDはharnessで対象3件を特定し、policyへ渡さない。ID・盤面hash・filenameによる答え分岐、固定Action列、ゲーム専用scriptを導入しない。
- private通常kernelを一回だけ実行する。Competition Rerun、公式提出、公式採点は行わない。
- per-game runtime上限1,200秒を超える/途中エラー時に同じrunを自動再試行しない。得られたartifactだけを保存する。

## 実施・受入条件

1. AGENTS.md、制御状態、現行v2.0指示、branch/HEAD/diff、version 5出力とC2-028を再読する。
2. source diffをoffline guardの件数・Action上限・表示ラベルだけに限定する。version 6をprivate通常実行として一回pushし、statusと出力を照合する。
3. 全3 IDでcandidate初期board/state/levelがversion 5と一致することを直接比較する。
4. per IDのversion5/version6 levels, actions, WIN/state, per-game runtime cap, generated-token telemetry, request/tool timeoutを記録し、差分を示す。
5. 160 Actionに達した結果とruntime 1,200秒に到達した結果を分ける。WINがなくても未達理由をaction horizon、runtime、timeout、またはその他に分類する。
6. 3件の私的試験だけから公開一般化・公式score・最終能力を主張しない。継続/不採用を一根拠で判定し、C2-030を一つ作成する。

## 事前結果

C2-027 version 5は同じ3件で`sk48` 0 level/69 Action/約1,200秒、`tn36` 0/80/468秒、`m0r0` 2/80/728秒。全件`gave_up`。同一開始状態は3/3直接照合済み。

## 実行記録

2026-10-23 19:52 UTCにprivate kernel version 6をpushし、直後のKaggle statusは`KernelWorkerStatus.RUNNING`。offline guard以外のnotebook sourceを変えず、version 5 sourceを`出力/ARC3-RUN-002-local/C2-029-source/v5-submission.ipynb`へ退避済み。変更Notebook SHA256 `fba57e12050751ab6b5ca0b31846110418a27a4e16da6fe82e52e0ae63c5345a`、version 5 backup SHA256 `5763f69d0794d7161dbe81a967edd2c10a6810c92ed1a28208bd47222fd5dfbc`。private/GPU有効/Internet無効を確認し、CLI run timeoutは7,200秒。結果待ち。

## 2026-10-23 21:13 UTC 最終結果

- Private kernel version 6は2026-10-23 21:06 UTC頃にCOMPLETE。Kaggleのread-only statusもCOMPLETE。対象ID・初期board/state/levelの照合は3/3一致。
- version 5の先頭3件から同じ順で比較：sk48 0→1 level、69→41 Action（-28）、tn36 0→3 level、80→160 Action（+80）、m0r0 2→0 level、80→160 Action（+80）。合計2→4 level（+2）、229→361 Action（+132）。3件の結果はすべてgave_up、WIN 0。確率的な別runの差であり、Action horizonを伸ばした因果効果とは断定しない。
- version 6のper-game elapsedは累積timerの隣接差からsk48 1,200.173秒、tn36 1,072.853秒、m0r0 927.513秒。sk48はruntime 1,200秒上限、残り2件は160 Action上限。sk48 transcript/logにはaction 42のread timeout（read timeout 36.05秒、tool call 0件保持）が1件。開始時analyzer ConnectionError後にretryも記録。timeoutがepisode失敗の単独原因とは断定しない。
- history generated_tokens合計は358,198。solver_note合計389,877でsk48に31,679差がある。3件すべてfinal_generated_tokens欄は0のため実消費量として不採用。v6 summaryのtotal tokensはhistory合計と一致。
- summaryの開始・終了時刻から求めたjob elapsedは3,200.794秒。一方summaryのtotal wallclock 6,673.7秒は、3件の累積final_wallclock_seconds合計6,673.737秒に一致しjob elapsedではない。同様にv5は実時間15,657.695秒に対しsummary 228,187.6秒で、25累積timerの合計228,187.620秒に一致する。根拠ある全体時間にはbenchmark start/endを使用し、per-gameは隣接する累積timer差を使う。
- v5/v6の出力manifestは全164/32ファイルを照合し、hash不一致・欠損0。audit JSONはC2-030で生成。
- v5 output manifest SHA256 1d7b5e3edce18cfd166b2040235d03f0a8bc030711e1c763a72a9687799f7372。v6 output manifest SHA256 b6fc5ddbb849f4f1e68bcaf6522797034a16e537bba2877d9c14697c771272e1。v6 benchmark SHA256 0731805ffb39f93a4962d7da248b9258f506438d3d57db53d71b8b810377bf75、log SHA256 465b19c609c68262a131a682e098452179e985869325eb9b05a8a1434955df17、comparison SHA256 fca997f9754045f089cead73f2df128e7ed8f82a4a95f80b498e7f43b139832d、Notebook SHA256 fba57e12050751ab6b5ca0b31846110418a27a4e16da6fe82e52e0ae63c5345a。
- 採否：horizon拡大はWINに結び付かず、ゲーム別差分も混在するため不採用。model/prompt/solver/HDS/official candidateは変更しない。Competition Rerun、公式提出、採点は未実施。
- 次工程はC2-030 telemetry監査。正本のbenchmark時間とsummaryの誤ったwallclock集計を機械判定し、今後の比較で使う時間/token列を確定する。