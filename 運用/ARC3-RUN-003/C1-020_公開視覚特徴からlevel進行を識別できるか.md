# C1-020 指示書：公開視覚特徴からlevel進行を識別できるか

- 指示ID：`ARC3-RUN-003-C1-020`
- 正本：v3.0／`ARC3-RUN-003`。旧版は履歴・参照用。
- Git基底：`main` HEAD `8667e9b9512e328084050007d3bdedb1ae5e245f`。既存dirty worktreeを維持し、stage/commit/resetなし。
- 公式状態：2026-10-24 01:33 UTC照会でC1-018 `57577905 PENDING`、score未提供。本日提出枠0。公式操作なし。

## 問い

C1-019でmodel v5の公開25環境に47件の公開level遷移を確認した。level進行直前の公開board構造と選択Action種別が、学習に使える一般的な予測情報を含むか。見たことのない環境へgroup-held-outした時にも、Action種別だけの基準を超えるかを測る。

## 対象と許可

- 保存済みC2-027 v5 OFFLINE public出力の25 event streamsのみをread-only利用する。trajectoryを再生しない。
- 各Actionに対して直前公開boardの色ラベル不変な構造量（値頻度の順位分布、異値隣接率、最頻値以外の行列広がり等）を抽出する。色番号、座標、盤面指紋、game/level ID、時系列番号は特徴量に含めない。
- 選択Actionは`ACTION1`〜`ACTION7`／`RESET`の一般カテゴリだけを比較用baseline特徴に使う。`action_display`や引数は読まない。
- 正解ラベルは保存event間でmodelに公開される`current_frame.level`が増えたかだけから算出する。`level`の絶対値は特徴にしない。`score`、`reward`、`level_completed`、`game_over`、`board_changed`、evaluator/hidden情報は参照しない。
- 5-fold group-held-outをrun単位で行う。run/file groupはtrain/test分離だけに使い、モデル入力・出力には保存しない。固定seedを用い、全モデルで同一foldを使う。
- 追加依存導入、HDS/runtime/policy/agent/model/prompt/Notebook/Kaggle変更は禁止。解析器/test/匿名aggregate/運転記録のみ許可。

## 比較と受入

1. 事前固定のbase-rate、Action-only、visual-only、Action+visualのL2 logisticモデルを比較する。ハイパーパラメータは結果を見て調整しない。
2. train foldだけで前処理をfitし、held-out環境のOOF予測を算出する。PR-AUCとBrier scoreを主指標とし、base-rateとAction-onlyに対する`delta`を記録する。
3. 視覚特徴を次のHDS/学習候補へ進める条件は、Action+visualがAction-onlyより全体PR-AUCを上げ、Brierを下げ、さらに5fold中4fold以上でAction-onlyを上回ること。満たさなければ現時点の予測signal不支持とする。
4. fold間で同一runが分割されないこと、特徴抽出が色番号の置換に不変であること、テスト時に識別情報や遷移後boardを使わないことをtargeted testsで検証する。
5. 出力は全fold・全環境を合算した匿名集計のみ。row予測、game/level ID、board、座標、action列、hash、個別foldの環境情報を保存しない。
6. signalが観測されても、これは行動選択への適応効果・学習成立・score改善の証拠ではない。C2は別指示書の仮説・受入・安全境界を固定してから行う。

## 終了条件

解析器とtargeted tests、OOF集計JSON、追記型運転記録を保存する。source/input/output SHA、previous/current/delta、採否と次の具体的な再開点を記録する。
