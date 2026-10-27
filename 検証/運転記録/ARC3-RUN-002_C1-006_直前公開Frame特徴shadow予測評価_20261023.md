# ARC3-RUN-002 C1-006 直前公開Frame特徴shadow予測評価

- 実施日: 2026-10-23 JST
- 指示: [C1-006指示書](../../運用/ARC3-RUN-002/C1-006_直前公開Frame特徴shadow予測評価.md)
- 判定: **Frame条件HDSはAction-only HDSより予測coverageを増やしたが、共通coverage上の正答は同一で、Action別多数派を超えなかった。runtime採用・holdout評価は不採用。**
- 範囲: 固定dev split先頭5公開環境、environment seed 31、policy seed 7/31/73、各最大80要求、GAME_OVER後SDK RESET。

## 方法と入力境界

環境/方針の組ごとに新規HDSを作り、直前SDK応答の公開Frame要約3値（複数Frame、中間grid差分、一時差分cell）を次Actionの条件へ追加した。比較対象のAction-only HDSは現在Action番号だけを条件とする。現在の応答結果は可視変化・level進行・新規盤面の真偽値で、訓練サンプルは各実行列の先頭75%、後半25%はread-only照会とした。Frame特徴は直前応答からのみ計算し、RESET結果と最初/比較不能な条件なしActionは除外した。

15実行（5環境×3 policy seed）で各seedの公開開始状態は5/5一致した。各seedで適格サンプル389件、学習289件、後半照会100件、合計照会300件/結果指標。環境別行・盤面・Frame列・識別子・予測条件値は保存していない。公開環境入力50ファイルの内容hash集合は F6D6B8A1EAD544554A8FDD1289090CA09A640661CA5298CF79B8AE5B0768F6AB。

## previous / current / delta

| 予測対象 | Action-only HDS previous coverage/正答 | Frame HDS current coverage/正答 | delta coverage/正答 | 共通coverage上の Action-only→Frame HDS | Action別多数派 |
|---|---:|---:|---:|---:|---:|
| 可視変化あり | 60/60 | 120/120 | +60 / +60 | 60件: 60→60 | 288/290 |
| level進行あり | 151/151 | 180/180 | +29 / +29 | 151件: 151→151 | 290/290 |
| 新規盤面あり | 60/60 | 100/99 | +40 / +39 | 60件: 60→60 | 238/290 |

Frame条件HDSが追加で覆った予測は可視変化60件、level進行29件、新規盤面40件で、そのうち新規盤面1件だけ誤答だった。一方、Action別多数派は照会300件のうち290件に適用でき、可視変化288件、level進行290件、新規盤面238件を正答した。両HDSの共通coverageでは3結果全てで正答数が同一で、Frame特徴による多数派の誤り修正は0件だった。

したがって予測coverage増加は観測されたが、同じ予測範囲上の判断改善は観測されず、より高coverageのAction別多数派を超えない。dev内の少数例であり、cross-game transfer、因果、公式scoreへの効果は示さない。事前条件不成立のため、未使用holdoutへ進めずruntimeへ接続しない。

## 検証・差分

- C1-006専用testsと関連するFrame診断/HDS shadow/no-op ablation tests: 12 passed。
- Ruff check/format、Python compile、CLI help: PASS。git diff --check: whitespace errorなし（既存CRLF/LF警告）。
- 評価器 SHA-256 dbd31f79d4609377db230abdbbb5c5cb31c7eb4c0338fa7eccfa2fe745b7c09f。
- test SHA-256 e6052aec09d7bfd9247183bc6ef4554f1526c5addf72f0b94e25e1561f44da72。
- 匿名aggregate 出力/ARC3-RUN-002-local/C1-006-frame-shadow-dev-summary.json SHA-256 969e17d3de3b2cc8eaf1f3baed1367184a118d2448acace29370ec8292ba980a。
- HDS、提出runtime/agent、candidate bundle、Notebook、kernel、保護対象状態は変更なし。公式Kaggle実行なし。

## 次工程

C5-001の次課題に沿い、read-onlyで境界層 接続/ARC3境界.py がSDKの複数Frameを保持するか確認する。HDS観測入力までに全gridが残り、既存診断と一致すれば、境界によるFrame情報損失仮説は閉じる。
