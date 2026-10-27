# ARC3 提出経路と現在状態

確認日: 2026-10-23 JST。現行の正本は [`運用/ARC3文書正本.md`](../運用/ARC3文書正本.md) が示す v2.0／`ARC3-RUN-002`。v1.0は履歴・参照用。

## 初回公式基準線

- Kernel `tecchannn/arc3-hds-hold-baseline` version 5、評価対象commit `f8ace66bec06440c21362b1afbf0dec0da99dd7f`。
- Competition Rerun submission `57527856`: `COMPLETE`、public score `0.00`。記録は [`ARC3-RUN-002_S1-初回公式基準線_20261022.md`](../検証/運転記録/ARC3-RUN-002_S1-初回公式基準線_20261022.md)。
- これはHDS候補を照会後にHOLDするbaseline。E4のplaceholder Parquet値は公式scoreではない。
- ARC-AGI-3の公式RHAEは、完了levelごとの人間基準作用数／agent作用数の二乗を基礎に、level番号で重み付けしてgame間平均を取る。公式説明ではscore `0%`は全ゲームでlevelを一つも完了しなかった状態。したがって基準線はhidden evaluationでlevel completionが0だった証拠で、ローカルのno-op削減だけでは改善判定にならない。定義は[ARC Prize scoring methodology](https://docs.arcprize.org/methodology)と[Kaggle evaluation](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/overview/evaluation)を参照。

## 最新公式提出結果

- Candidate kernel `tecchannn/arc3-observation-driven-exploration-candidate` version 4のCompetition Rerun submission `57541830`は2026-10-23 00:03:01 UTCに受理され、`COMPLETE`、public score `0.25`。公式履歴を2026-10-23 00:20 UTCに再照会して確認した。
- 初回baseline `57527856`のpublic score `0.00`に対し、公開score差分は`+0.25`。Kaggle APIの`privateScore`は空欄で、非公開scoreは未確認。
- 提出後quotaは`numToday=1`, `numTotal=5`。この公式scoreは候補kernelの通常実行状態やplaceholder Parquetから推定していない。

## 現行ローカル候補

- C2-001の観測駆動探索Actionを追加し、HDS HOLDと分離した公開Action経路を構成した。HDS候補や自己申告の実行許可はAction認可に使わない。C3-001で公式SDK RESETによるGAME_OVER再試行、C3-002で座標色枯渇時に適格な別色を選ぶ処理を加えた。
- C3-001/002は同じ20 holdoutをseed 7/31/73で評価。探索最大levelは各1/2/2、WINはいずれも0。seed73のpolicy holdは1から0へ減り、holdout要求は1550から1600になった。違法Action・重複stepは0。Kaggle scoreは未測定。
- C2とC3の記録: [`C2評価`](../検証/運転記録/ARC3-RUN-002_C2-探索Action評価_20261023.md)、[`C3-001`](../検証/運転記録/ARC3-RUN-002_C3-001_GAME_OVER再試行評価_20261023.md)、[`C3-002`](../検証/運転記録/ARC3-RUN-002_C3-002_座標色枯渇fallback評価_20261023.md)。
- C2-003ではno-op罰だけを `-0.5` から `-1.0` に変更。holdoutはseed 7/31/73各20ゲームでlevels 5→5、no-op 460→415（-9.8%）、level完了Action 128→118、RESET/GAME_OVER 27→29、WIN 0。公式scoreへの改善は未確認。結果を候補version 4へ反映した。
- C4-001のレベル間転移ablationではcarry/resetともholdoutのcompleted levels 2、完了Action位置は同一。carryはno-opが10少ない一方GAME_OVERが1多く、優位は未確認のためversion 4の現行carryを維持した。詳細は [`C4-001`](../検証/運転記録/ARC3-RUN-002_C4-001_レベル間転移評価_20261023.md)。
- C4-002では同一ゲーム内のlevel進行時に色UCB統計だけを消すdev比較を実施。完了levelは各seed1のまま、GAME_OVERは18→16だがno-opは35のまま。no-op改善条件を満たさずholdout未実施・不採用。詳細は [`C4-002`](../検証/運転記録/ARC3-RUN-002_C4-002_レベル間色統計評価_20261023.md)。
- C4-003で同じ色統計resetを固定holdout20環境×seed7/31/73へ評価した。完了levelsは5のまま、GAME_OVERは29→27だがno-opは415→444へ増えたため不採用し、version 4を維持した。詳細は [`C4-003`](../検証/運転記録/ARC3-RUN-002_C4-003_色統計resetGAME_OVER転移確認_20261023.md)。
- C2-013は同色4近傍あり座標を優先するdev比較で、完了levelsが3→0、no-opが35→36となり不採用・holdout未実施。近傍bucketを絞っても進行は再現せず、version 4を維持した。詳細は [`C2-013`](../検証/運転記録/ARC3-RUN-002_C2-013_ACTION6同色近傍評価_20261023.md)。
- C2-014はGAME_OVER応答へUCB罰`-1.0`を足すdev比較で、GAME_OVERは18→19、no-opは35→34、完了levelsは3を維持した。終端低下条件を満たさず不採用・holdout未実施。詳細は [`C2-014`](../検証/運転記録/ARC3-RUN-002_C2-014_GAME_OVER報酬評価_20261023.md)。
- C2-015はACTION6後GAME_OVER 15件の公開特徴を診断し、相対中心距離middle bucketに13件（seed別4/4/5）が集中した。C2-016で同色近傍3_4との重なりが9件と確認されたが、因果は未確認。座標規則・報酬係数を追加せずcandidate v4維持、holdout未実施。詳細・匿名aggregateは [`C2-015`](../検証/運転記録/ARC3-RUN-002_C2-015_ACTION6_GAME_OVER特徴診断_20261023.md)。
- C2-016交差集計でmiddle×同色近傍3_4はACTION6 208回中GAME_OVER 9回（seed別4/3/2）だったが、同じbucketにlevel進行も1件含まれた。安全な回避規則として採用せずcandidate v4を維持。詳細は [`C2-016`](../検証/運転記録/ARC3-RUN-002_C2-016_ACTION6_GAME_OVER特徴交差集計_20261023.md)。
- C2-017の中間頻度色遅延はdevで介入機会0回、levels/no-op/GAME_OVERに差なし。no-op・GAME_OVER低下条件を満たさずholdout未実施・不採用、candidate v4維持。詳細・匿名aggregateは [`C2-017`](../検証/運転記録/ARC3-RUN-002_C2-017_ACTION6中間頻度色評価_20261023.md)。
- C2-018は固定dev 5環境×seed7/31/73で、no-op35件中に公開`available_actions`変化・state変化は各0件。`full_reset` flag差分5、frame数差分17は別記録し、Action集合変化の仮説を支持せず候補policyは変更していない。candidate v4を維持し、公式Competition Rerunを待つ。詳細・匿名aggregateは [`C2-018`](../検証/運転記録/ARC3-RUN-002_C2-018_no-op報酬と公開Action集合変化監査_20261023.md)。
- C2-004の可視変化報酬 `0.25→0.0` は開発5環境×3 seedでseed31のlevel進行を失い、no-opも増加。不採用でholdout未実施。runtime既定値と候補version 4は維持した。詳細は [`C2-004`](../検証/運転記録/ARC3-RUN-002_C2-004_可視変化報酬評価_20261023.md)。
- C2-005のレベル進行報酬 `4→8` はcompleted levels、完了Action位置、no-opが全seedで同じ。GAME_OVER減は1/3 seedだけのため不採用・holdout未実施。version 4を維持した。詳細は [`C2-005`](../検証/運転記録/ARC3-RUN-002_C2-005_レベル進行報酬評価_20261023.md)。
- C2-006のAction6初手優先は開発5環境×3 seedでno-opを35→23に減らしたが、completed levelsを3→2へ落としGAME_OVERを1増やした。不採用・holdout未実施。version 4の現行順を維持した。詳細は [`C2-006`](../検証/運転記録/ARC3-RUN-002_C2-006_座標Action初手評価_20261023.md)。
- C2-007はUCB係数0.4でholdoutのno-opが415→425となり不採用。C2-008の同盤Action回避、C2-009の座標色UCB係数分離も開発条件を通らず不採用。HDSの公開遷移shadow照会は多数派基準を上回らず、runtimeへ接続しない。
- C2-010では固定holdout 60 runの進行5件すべてにAction 6が関与したが、Action 6のno-opは1,183件中278件。応答後の可視変化以外に次Actionの一般化可能な選択特徴は得られず、新しい規則は採用しなかった。後続評価一覧は [`2026-10-23後続状態確認`](../検証/運転記録/ARC3-RUN-002_20261023後続状態確認.md)、診断詳細は [`C2-010`](../検証/運転記録/ARC3-RUN-002_C2-010_公開進行遷移集約診断_20261023.md)。
- C2-011でdev ACTION6 703回のクリック座標を匿名特徴集計した。中心bucket155回中2回で進行し、seed7/73に反復した一方、seed31は中間距離bucketで進行。全成功3件のため一般則とは判定しなかった。続くC2-012の中心距離順ablationはdevで完了levelが3→1、no-opが35→37となり不採用、holdout未実施。candidate version 4を維持した。詳細は [`C2-011`](../検証/運転記録/ARC3-RUN-002_C2-011_ACTION6座標特徴診断_20261023.md) と [`C2-012`](../検証/運転記録/ARC3-RUN-002_C2-012_ACTION6中心距離順評価_20261023.md)。
- C5-001では前回holdout 60 runが全て80 Action上限で停止した事実を起点に、公開dev5環境×3 seedを80/160/320で比較。完了levelsは全条件3のまま、no-op 35→84→193、GAME_OVER events 18→52→105、illegal/duplicate/HOLDは0。上限拡大は不採用でversion 4の80 Actionを維持。holdoutとKaggle候補は更新していない。詳細は [`C5-001`](../検証/運転記録/ARC3-RUN-002_C5-001_Action上限診断_20261023.md)。
- C1-003では2,000応答中654件（32.7%）が複数gridで、15/25公開環境に存在。C1-004は全25環境×3 seed・6,000応答を再監査し、no-op 450件中219件（48.7%）が最終gridと異なる中間gridを含むことを確認した。この重複は全seedで再現し、ACTION6が205/219件を占める。C1-005のdev一要因ablationはno-op合計35→34、減少は1/3 seedに限られ不採用。candidate v4は維持し、holdoutへ進まない。途中gridの意味と進行への因果も未確認。詳細は [`C1-003`](../検証/運転記録/ARC3-RUN-002_C1-003_複数Frame監査_20261023.md)、[`C1-004`](../検証/運転記録/ARC3-RUN-002_C1-004_Frameとno-op重複監査_20261023.md)、[`C1-005`](../検証/運転記録/ARC3-RUN-002_C1-005_中間Frame差分no-op罰ablation_20261023.md)。
- `.venv`での開発環境監査はPython 3.12.10、依存読込、Parquet/PNG、Kaggle配布照合を含め合格。
- 統合検証: `uv.lock --check`、127依存check、全体Ruff、compileall合格。全体pytest `400 passed, 44 skipped, 35 subtests passed`。公開環境のoffline smokeと認証付きKaggle read-only監査もpass。詳細は [`2026-10-23後続状態確認`](../検証/運転記録/ARC3-RUN-002_20261023後続状態確認.md)。
- Kaggleの登録結果によりkernel slugを `tecchannn/arc3-observation-driven-exploration-candidate` に統一した。初回基準線kernel/versionは上書きしない。
- latest candidate: version 4、`出力/ARC3-SUBMIT-010`。source bundle SHA-256 `974029af7f66b774c96af3cf86b2344905bf68a0c83445fd366c74dd779e54d9`、Notebook SHA-256 `c07059b242eccd77dcf1c482662e852db77edd86b80e7a5e231f138773f3b10b`。35ソースの静的閉包を含み、認証markerは含まない。
- version 4の通常実行は `COMPLETE`、35ソース検証済み、Tracebackなし。Parquetは前版と同じplaceholder（SHA-256 `688e716e8f9ad967f6211a3796070b69c74a5adb5ce93e9f1c0ba77701ea3194`）で、Competition scoreではない。実行証拠と日次枠は [`ARC3-RUN-002_Kaggle通常実行_20261023.md`](../検証/運転記録/ARC3-RUN-002_Kaggle通常実行_20261023.md)。
- version 4のNotebook埋込bundleを再読込し、bundle SHAとmanifest記載の35 source SHA全件の一致を確認。候補agent sourceは現行ローカルと一致し、探索方針はC2-003でローカル検証したSHAを保持。後続の未採用ablationコードはversion 4に含めない。証跡は [`2026-10-23後続状態確認`](../検証/運転記録/ARC3-RUN-002_20261023後続状態確認.md)。

## Notebook再生成・検証

```powershell
.venv/Scripts/python.exe 道具/ARC3提出物構築.py `
  --owner tecchannn `
  --output-dir 出力/ARC3-SUBMIT-011
```

新しい採用済み改良を候補化するときだけ未使用の次ディレクトリを使う。現在のversion 4の生成物は `出力/ARC3-SUBMIT-010` に保存している。生成物は `submission.ipynb`、`kernel-metadata.json`、`bundle-manifest.json`。source bundleは静的import閉包のみとし、`入力/`、`記憶/`、`検証/`、秘密情報は含めない。`ARC3-SUBMIT-001`〜`010` は保持する。Save & Run AllはOFFLINE import確認とplaceholder Parquet生成のみで、Competition Rerunやscoreの証拠ではない。

```powershell
.venv/Scripts/python.exe -m kaggle kernels push --path 出力/ARC3-SUBMIT-011
.venv/Scripts/python.exe -m kaggle kernels status tecchannn/arc3-observation-driven-exploration-candidate
.venv/Scripts/python.exe -m kaggle kernels output tecchannn/arc3-observation-driven-exploration-candidate/5 `
  --path 出力/ARC3-SUBMIT-011/kaggle-output
```

Competition RerunはNotebookの保存・通常実行とは別操作。実行前に提出枠を確認し、利用可能ならversion 4を提出する。

```powershell
.venv/Scripts/python.exe -m kaggle competitions submission-limits arc-prize-2026-arc-agi-3
.venv/Scripts/python.exe -m kaggle competitions submit arc-prize-2026-arc-agi-3 `
  --file submission.parquet `
  --kernel tecchannn/arc3-observation-driven-exploration-candidate `
  --version 4 `
  --message "ARC3-RUN-002 observation-driven exploration v4"
.venv/Scripts/python.exe -m kaggle competitions submissions arc-prize-2026-arc-agi-3 --format json
```

Kaggleの日次上限1件は[staffの説明](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/discussion/705198)と`submission-limits`で確認した。Kaggle Overviewで確認したentry deadlineは2026-10-26 23:59 UTC（10-27 08:59 JST）、final submission deadlineは2026-11-02 23:59 UTC（11-03 08:59 JST）。期限は変更され得るため、次回提出前にも[競技Overview](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/overview)を再確認する。資格情報はrepository、Notebook、ログへ記録しない。

## 2026-10-23 12:29 UTC read-only再確認

- `submission-limits`: 本日1件使用、累計5件、残り0件。`submissions`最新はcandidate v4 submission `57541830`（COMPLETE、public `0.25`）、baseline `57527856`（COMPLETE、public `0.00`）。新規提出はない。
- candidate kernelのcurrent statusは`COMPLETE`。privateScoreは引き続き空欄。日次枠が0のため、次の提出は枠更新後に行う。
- Kaggle CLI 2.2.4から2.2.5への更新警告が出たが、認証済みread-only照会は成功した。固定環境は変更していない。
- 公式Overviewを再確認し、entry deadline `2026-10-26 23:59 UTC`、final submission deadline `2026-11-02 23:59 UTC`を確認。一次資料は上記公式Overviewとstaffの日次上限説明。

## 2026-10-23 13:54 UTC private研究候補の確認

- 別系統の汎用モデル候補 `tecchannn/arc3-model-guided-c2-025` はprivate kernel version 3まで通常実行完了。最新のoffline smokeは公開環境1件で84 Action、8 level中0完了、score 0.00。通常kernelのParquetは公式scoreではない。
- C2-025の目的であるKaggle/Python 3.12/GPU/model/server/ARC runtimeの起動確認は通ったが、現在の公式候補v4に対する能力改善は確認できず、公式候補へ反映していない。根拠は[実行記録](../運用/ARC3-RUN-002/C2-025_汎用モデル推論候補のオフライン起動確認.md)と、出力記録 `出力/ARC3-RUN-002-local/C2-025-kaggle-output/v3/`。
- read-onlyの競技submission historyは引き続きcandidate v4 `57541830`（COMPLETE, public `0.25`）とbaseline `57527856`（COMPLETE, public `0.00`）が最新。C2-025はprivate kernelであり新規competition submission・採点は行っていない。

## 2026-10-23 15:05 UTC private汎用モデル候補の3環境比較と25環境pilot

- model-guided candidate kernel version 4のprivate通常実行はCOMPLETE。3公開環境・各80 Actionでcandidateは3 level、local v4は1 level（delta +2）、WIN 0。後続の開始盤面監査でcandidateとlocal baselineのinitial board/state/levelが3/3一致した。開発評価であり公式scoreではない。詳細は[`C2-026`](../運用/ARC3-RUN-002/C2-026_汎用モデル候補の公開3環境action一致比較.md)。
- 3環境のdeltaを受け、offline-only guardを25環境に拡大したkernel version 5を2026-10-23 14:58 UTC頃にprivate通常実行としてpush。15:05 UTCの最新確認はRUNNING。80 Action/環境、逐次1 pass、per-game 1,200秒、CLI timeout 31,920秒。出力回収後、baselineとのID集合・開始盤面・完了levelを照合する。詳細は[`C2-027`](../運用/ARC3-RUN-002/C2-027_汎用モデル候補の公開25環境pilot.md)。
- 公式Competition Rerun履歴を2026-10-23 15:43 UTCに再確認。最新candidate v4 `57541830` COMPLETE/public `0.25`、baseline `57527856` COMPLETE/public `0.00`。上記private runに伴う新規公式提出はない。汎用モデル候補は公式候補へ昇格していない。

## 2026-10-23 19:44 UTC private 25環境pilot完了

- model-guided candidate kernel version 5はprivate通常実行で`COMPLETE`。公開25環境すべてでbaselineとのinitial board/state/levelが一致。
- 同一ID集合でcandidateは47 completed levels/1,906 Action、local v4 baselineは3/2,000（差分+44）。22改善・2同等・1後退、WIN 0、全candidate run stateは`gave_up`。4環境がper-game 1,200秒上限に到達した。これは開発用private評価であり、公式scoreではない。
- Kaggle outputは`出力/ARC3-RUN-002-local/C2-027-kaggle-output/v5/`に保存し、全164ファイルのSHA256 manifestとper-game comparison JSONを作成。詳細は[`C2-027`](../運用/ARC3-RUN-002/C2-027_汎用モデル候補の公開25環境pilot.md)。
- 実行後のread-only Competition submissions照会もlatest candidate `57541830` public `0.25`、baseline `57527856` public `0.00`のまま。新規公式提出・採点は未実施。candidateは公式候補へ昇格せず、次は[`C2-028`](../運用/ARC3-RUN-002/C2-028_25環境pilotの失敗分布と実行上限診断.md)で失敗・上限分布を診断する。

## 2026-10-23 19:52 UTC C2-028診断とC2-029 private run

- C2-028はC2-027の25環境を同一開始状態で再集計し、22改善・2同等・1後退、candidate 47 level/1,906 Action、baseline 3/2,000、WIN 0、4件のruntime上限到達を確認。private開発評価であり公式scoreではない。詳細は[`C2-028`](../運用/ARC3-RUN-002/C2-028_25環境pilotの失敗分布と実行上限診断.md)。
- 80 Action上限の影響を調べるC2-029としてoffline guardだけを変更し、private kernel version 6を19:52 UTCにpush。対象は従来と同じ先頭3公開環境、160 Action/環境、1,200秒/環境、逐次1 pass。push時statusは`RUNNING`。変更Notebook SHA256 `fba57e12050751ab6b5ca0b31846110418a27a4e16da6fe82e52e0ae63c5345a`。version 5 sourceは`出力/ARC3-RUN-002-local/C2-029-source/v5-submission.ipynb`に保存。
- C2-029は通常private runであり、Competition Rerun・公式提出・採点は未実施。latest official historyは再確認済みの`57541830` public `0.25`と`57527856` public `0.00`。


## 2026-10-23 21:13 UTC C2-029完了・C2-030 telemetry監査

- model-guided private kernel version 6 COMPLETE。3/3の初期状態一致、levels 2→4（+2）・actions 229→361（+132）だが、個別deltaは+1/+3/-2、WIN 0、全run gave_up。160 Actionへ広げた効果と断定できず候補変更なし。公式候補へ昇格せず。
- 同じv5/v6 summaryでtotal wallclockが累積clock総和を出す不整合を確認。benchmark時刻差は15,657.695秒/3,200.794秒で、summary値は228,187.6秒/6,673.7秒。C2-030ツールを追加し、今後はbenchmark時刻差とcumulative clock差分を使う。summary tokenはhistoryと一致するがsolver_note差分が残り、final_generated_tokensは全0のため、不正確な列を性能評価へ使用しない。
- 新規の詳細記録: [C2-029](../運用/ARC3-RUN-002/C2-029_80Action打切りと勝利未達のhorizon検査.md)、[C2-030](../運用/ARC3-RUN-002/C2-030_benchmark-wallclock-token-telemetry整合性監査.md)。audit JSONは出力/ARC3-RUN-002-local/C2-030-telemetry-audit/。
- Kaggle read-only確認ではprivate kernel COMPLETE、公式score履歴は57541830 public 0.25、57527856 public 0.00、当日残り0。公式再提出・採点なし。次工程C2-031でv6 sk48 runtime-cap時系列を既存ログから分解する。
## 2026-10-23 21:21 UTC C2-031 cold-start診断・C2-032 private run開始

- C2-031はv6 sk48の1,200.173秒runtime、36.05秒read timeout 1件、turn-token-budget yield 7件を確認した。全run request logは191 request/190 responseだが、request単位の時刻・game IDがなくwait内訳の再構成は不可。server precache 185.40GB/876.95秒、analyzer初回ConnectionError、Notebook既存の8m32s cold-load記録は、first-game timer中のstartup重複と整合。timeoutだけを原因とせず、根因はprivate readiness testへ進める。記録は[C2-031](../運用/ARC3-RUN-002/C2-031_sk48-runtime-cap-analyzer待ち時間監査.md)。
- C2-032はNotebook cell13 readiness probeとoffline-only cell18 capだけ変更し、private kernel version 7をpush。直後status RUNNING。初期条件はsk48単一公開環境、160 Action/1,200秒。Notebook SHA d83af86310b2e76993fc16ec3db3e0c1862f1a517dbb50d0b411f20b38a60922、v6 backup fba57e12050751ab6b5ca0b31846110418a27a4e16da6fe82e52e0ae63c5345a。公式提出・採点・Competition Rerunなし。詳細は[C2-032](../運用/ARC3-RUN-002/C2-032_SGLang推論ready前のgame-timer消費を避けるprivate-pilot.md)。
## 2026-10-23 21:37 UTC C2-032失敗保存・C2-033 version 8開始

- C2-032 private kernel version 7は`ERROR`。38 weight shard中34 shard（89%）を11分15秒までに読み込んだが、server launch後720秒でreadiness未確認のfail-closedが発火し、offline benchmarkは開始されなかった。`/health_generate` HTTP 200未観測のためroute故障とは判定しない。v6 sk48とのperformance deltaは取得不能。
- 回収ログを`出力/ARC3-RUN-002-local/C2-032-kaggle-output/v7/`に保存。kernel log SHA256 `24ae6a54f64977729d5b074e58fa9562fe44bce53bd8ecc49742bd098165a6af`、serve.log SHA256 `e2b578339fd168e08b6c1bdebf197990124dc65f8f3bb0504272b8ff21762d40`。詳細は[C2-032](../運用/ARC3-RUN-002/C2-032_SGLang推論ready前のgame-timer消費を避けるprivate-pilot.md)。
- C2-033でreadiness deadlineを12分から18分へ限定延長。変更Notebook SHA256 `449b57c9eca8f24a6338b5eb6f68d231a2fab4185073293a79c00581f85a5a05`。差分はcell 5のdeadline値とcell 18のoffline labelのみ。version 8 push成功、直後status `RUNNING`。task指示書は[C2-033](../運用/ARC3-RUN-002/C2-033_SGLang-cold-start-deadline延長private-pilot.md)。
- private kernel run。Competition Rerun、公式提出、採点なし。公式candidate昇格なし。
