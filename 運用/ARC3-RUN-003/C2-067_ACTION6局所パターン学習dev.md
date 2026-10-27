# C2-067 — ACTION6の局所公開パターン学習

## 問い

現行HDS順位照会は、座標引数の構造がないためACTION6を学習・順位付け対象から除外する。座標をcolor IDや固定位置でなく、公開盤面の局所構造・色頻度・端/内部カテゴリで特徴化し、未見公開ゲームのACTION6座標候補に結果分布を転移できるかを測る。

## 固定条件

- C2-065/066と同じ公開split seed `20261027`。train 5公開ゲーム×40 Actionから座標特徴別の報酬件数/平均を学習。devは未見5ゲーム×seeds `7,31,73`、80 Action上限で現行探索器とpaired比較する。
- Featuresは色占有率bucket、同色8近傍数bucket、盤面端/内部だけ。game/level ID、color number、座標そのもの、固定action列を保存しない。
- candidateは同色・同盤面の未試行座標集合内で、事前・オンラインの局所特徴別期待報酬とUCBを使って1座標を選ぶ。Action番号・色選択統計・合法性は既存policyのまま。
- 同一初期盤面・合法集合・seedを確認。primary metricは公式EnvironmentScoreCalculatorのRHAE。dev gateは平均差`>= +0.01`、score improvement数がregression数以上、level/WINを減らさず、illegal/duplicate/errorが0。
- 特徴別support、action trace変化、memory hash、no-op、進行levelを記録する。

## 採否

gate未達なら座標学習を棄却し、runtime/Notebookへ接続しない。通過時のみ残り未見15ゲームで同条件holdoutを行う。改善しない件数変化は性能改善と扱わない。

## 境界

公開SDK観測のみ。モデル状態に識別子や盤面位置を保存しない。Kaggle submission/quota、Notebook/kernel変更なし。
