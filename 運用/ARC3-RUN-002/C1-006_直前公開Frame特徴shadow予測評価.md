# C1-006 指示書：直前の公開Frame特徴によるshadow予測評価

- 指示ID: ARC3-RUN-002-C1-006
- 版: 1.0／2026-10-23（JST）
- 根拠: C1-002のAction番号のみを条件としたHDS予測はAction別多数派を超えなかった。C1-003/004で公開応答内に複数Frameと中間差分を確認したが、次応答の予測情報になるかは未検証。

## 目的

現在のAction番号だけの予測へ、ひとつ前の公開応答から計算したID-free Frame特徴を加え、同じdev実行列の後半応答でAction別多数派およびAction-only HDSと比較する。特徴は予測対象応答より前に利用可能な値だけとし、同一応答のFrameや結果を入力へ混ぜない。

## 対象・方法

- 固定dev split: split seed 20261022の先頭5公開環境。環境seed 31、policy seed 7/31/73、各80要求、GAME_OVER後はSDK RESET。
- 各環境・policy seedごとに独立HDSを使い、時系列サンプル先頭75%で学習、後半25%をread-only照会する。
- baseline HDS条件は現在のAction番号のみ。試験HDS条件には現在のAction番号と直前応答の「複数Frameあり」「中間gridが最終gridと異なる」「一時差分cellあり」の真偽値だけを加える。
- 結果は現在の応答の公開要約である「可視変化あり」「level進行あり」「新規盤面あり」。Action別多数派も同じ訓練・照会分割で算出する。
- RESETの結果は学習対象から除外するが、その公開Frame要約は次Actionの直前公開応答特徴として扱える。最初のAction、比較不能な直前応答は予測対象から除外する。
- 指標は照会件数、各HDSの単一予測coverage/正答、同じcoverage上でのAction-only／frame条件HDSと多数派の正答、frame条件がAction多数派の誤りを正した件数。ゲームごとに独立集計し、出力はseed別aggregateのみ。

## 保持条件・反証

- 盤面、色、座標、game/level ID、GUID、hash、trajectory、hidden/evaluator情報を入力・出力へ残さない。出力JSONにも生応答・環境別行・予測条件値を含めない。
- HDS、提出runtime、探索方針、Notebook、kernel、candidate bundle、保護対象状態は変更しない。公式Kaggle操作は行わない。
- frame特徴を現在応答から作るリーク、RESETを予測対象へ含める誤り、baselineとの分割不一致をテストで反証する。
- frame条件HDSがmatched coverage上のAction-only HDSとAction多数派の双方を上回らない場合は、特徴をruntimeへ採用しない。少数標本・同一dev内の結果を一般化や公式改善として主張しない。

## 成果物

評価器、targeted test、匿名aggregate JSON、source SHA-256、previous/current/delta、採否をC1-006運転記録へ保存する。失敗・予測なしも全て記録する。
