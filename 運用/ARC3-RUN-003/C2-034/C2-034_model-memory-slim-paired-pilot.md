# ARC3-RUN-003 C2-034: slim memoryのlevel内・level間適応paired pilot

## 目的と優先根拠

公式基準B1はcandidate v4、提出`57541830`、public `0.25`。公式APIは提出単位のscoreのみを返し、game/level内訳とprivate scoreは未観測であるため、この試験を公式scoreの原因証明とは扱わない。

private model-guided v5は公開25環境で同一開始状態を25/25照合し、baseline 3から47 levelsへ進んだ一方、WIN 0・全25件`gave_up`だった。v6でAction上限を160へ広げても3件の結果は1/3/0 levels・WIN 0で、horizonの因果改善は確認されなかった。現行model Notebookは`ARC3_MEMORY_SECTIONS=off`としており、解析コード上この設定は永続memory機構（section guidance、記録、再注入）を無効化する。そこでv3の記憶→推論→適応要件に直接関わる一要因として、World modelとPlanだけを保持する`slim`を、同一条件の`off` controlと比較する。

これは内部公開ゲーム上の反証可能な候補検査であり、HDS・公式candidate v4への採用、公式scoreの原因帰属、private/hidden評価への一般化を意味しない。

## 仮説

同じmodel・solver・Action/runtime上限・開始状態で、`ARC3_MEMORY_SECTIONS=slim`は`off`よりlevel-completion総数を増やす。改善がなければ、この設定差は現時点で優先故障とみなさない。

## 変更範囲

- 起点は現行private kernel version 8のNotebook（SHA-256 `449b57c9eca8f24a6338b5eb6f68d231a2fab4185073293a79c00581f85a5a05`）。元Notebookとmetadataは変更しない。
- `off` controlと`slim` treatmentの2コピーを作る。両方でoffline game limitを3、`LOCAL_ANALYZER_SEED=0`とし、C2-033の`SERVER_STARTUP_TIMEOUT=1080`、実推論readiness probe、160 Action、1 gameあたり1200秒、1 pass、逐次実行を同一にする。
- arms間の唯一のsolver差は`ARC3_MEMORY_SECTIONS`（`off`対`slim`）。温度0.6、top-p 0.95、model、prompt、server、tools、level-transfer guidanceは維持する。
- Kaggle kernelは既存のprivate `tecchannn/arc3-model-guided-c2-025`のみを使い、version 9 controlを完了・出力取得してからversion 10 treatmentを一度だけ実行する。GPU有効、Internet無効、Competition Rerun無効。公式提出を行わない。
- 公開25環境の先頭3件をHarnessの評価対象として使う。game IDは開始状態・出力の対応照合だけに使い、model/policyには渡さない。`記憶/事前記憶/v0.4`、answer map、trajectory、hidden情報は読み込まない。

## 観測・受入条件

1. 2 Notebookのsource diffを機械検査し、上述の共通offline設定以外のsolver動作差がmemory modeだけであることを確認する。
2. 各armの3件でinitial board/state/levelを直接照合し、3/3一致しない場合は比較不成立とする。
3. completed levels、WIN、Actions、no-op、GAME_OVER、runtime、generated tokens、request/tool timeoutをper-gameと合計で`off previous / slim current / delta`として記録する。集計scoreやkernel `COMPLETE`だけを能力証拠にしない。
4. `slim` armでWorld model/Planのmemory updateが観測され、更新後のpromptへ再注入された証拠を取る。実際の更新・再注入がなければ実験不成立。
5. pilot継続条件は、合計level deltaが正、WIN件数が減らず、更新・再注入が成立し、ゲーム開始不一致・illegal action・runtime上限不明がないこと。条件を満たしても3ゲーム1 seedなのでruntime採用・公式提出を行わず、別seedの再現試験を次taskにする。
6. level deltaが0以下、WINが減る、またはmemory更新が成立しない場合は仮説不支持または比較不成立として閉じ、探索係数・Action列・game-specific条件へ逃げない。

## 終了条件

2 armsのKaggle status/output、Notebook・log・event/summary hash、paired starts、previous/current/delta、採否と次taskを追記専用結果記録へ保存する。公式履歴が不変であることをread-onlyで確認する。このprivate pilotは公式score・HDS学習成立・提出候補採用を主張しない。
