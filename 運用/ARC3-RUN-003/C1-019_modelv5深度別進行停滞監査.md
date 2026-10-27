# C1-019 指示書：model v5公開25環境の深度別進行停滞監査

- 指示ID：`ARC3-RUN-003-C1-019`
- 正本：v3.0／`ARC3-RUN-003`。旧版は参照用。
- 初期基底：`main` HEAD `8667e9b9512e328084050007d3bdedb1ae5e245f`。既存dirty worktreeを保持し、stage/commit/resetをしない。
- 公式状態：2026-10-24 01:24 UTC read-only照会でC1-018 `57577905 PENDING`、public/private score未提供。B1 `57541830 COMPLETE/public 0.25`、B0 `57527856 COMPLETE/public 0.00`。本日提出枠0。Kaggleへの書込みなし。

## 問い

C2-027 model v5公開25環境のlocal評価は47 level完了・WIN 0だった。進行停止が可視無変化Actionの反復に偏るのか、level深度が増すほど完了率が低下するのかを、保存済み公開観測だけで切り分ける。

## 許可範囲

- `出力/ARC3-RUN-002-local/C2-027-kaggle-output/v5/` の保存済みOFFLINE public benchmarkと25 event logsをread-only集計する。modelに渡された保存promptで`current_frame.level`が公開されていることを先に確認済み。
- 評価器・hidden値・score/reward・`level_completed`等の評価用ラベルは使わず、eventの公開`board`、現在`level`、`state`、Action応答順だけから可視変化とlevel遷移を独立に算出する。
- outputは25環境を結合した匿名aggregateのみ。game/level ID、filename、board、hash、action座標、trajectory、個別環境集計は保存しない。level深度は共通の整数ordinalで集計してよい。
- 新規Kaggle操作、Notebook/model/prompt/runtime/HDS/policy/agent変更は禁止。

## 検証・受入

1. 入力manifest、benchmark、25 event logのSHA256とファイル件数を記録する。
2. 初期・各応答の公開board/levelを前状態と比較する。Actionは直前の公開levelへ帰属し、levelが進んだ場合は公開level遷移を完了として数える。`score`、`reward`、評価器内部値は参照しない。
3. Action総数・level遷移数・WIN数が保存済みC2-027記録と矛盾しないかaggregateで照合する。採点値の再計算は行わない。
4. level深度ごとに開始環境数、完了環境数、Action数、可視変化数、可視無変化数を算出する。可視無変化率を全体・深度別に比較する。
5. 出力から識別子・盤面・座標・trajectory・禁則keyを監査する。入力破壊がないこととGit差分を確認する。
6. この診断は原因の局所化のみ。性能改善・公式score因果・HDS学習・C2支持を主張しない。新規変更は、結果から一意に支持された故障がある場合だけ別指示書を作成してから行う。

## 終了条件

source/input/output SHA、匿名集計、previous/currentの位置づけ、差分、限界、targeted検算結果、採否、再開点を追記型C1-019運転記録へ保存する。
