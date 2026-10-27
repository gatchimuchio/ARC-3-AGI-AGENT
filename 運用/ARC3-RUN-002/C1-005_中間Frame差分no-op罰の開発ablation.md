# C1-005 指示書：中間Frame差分を含むno-op罰の開発ablation

- 指示ID: `ARC3-RUN-002-C1-005`
- 版: 1.0／2026-10-23（JST）
- 根拠: C1-004で複数grid no-op 219/450件を全3 seedに観測。ACTION6に205件、ACTION1/3/5にも各seedで反復し、level進行8件も複数gridだった。
- 比較: candidate v4既定のno-op報酬 `-1.0` 対、非RESET・最新盤面不変・level増分なし・いずれかの中間gridが最終gridと異なる場合だけ罰を `0.0` とする試験条件。

## 目的

途中gridが変化して最終盤面へ戻るno-opを、常に失敗報酬とみなさない効果をdevで分離する。これは公開状態から作る局所報酬ablationであり、途中gridの意味や能力改善を前提にしない。

## 許可する範囲

- `検証/ARC3探索Actionローカル評価.py` にローカル評価専用の一要因flagを加える。試験方針は既定報酬の計上後、中間grid条件を満たすno-opに限りAction UCBとACTION6色UCBの報酬集計をそれぞれ+1.0補正する。
- 開発split先頭5公開環境、seed 7/31/73、80 Action要求、GAME_OVER後RESETを同条件の基準・試験方針で比較する。各seed・各環境で公開開始盤面と合法Action集合の一致を確認する。
- 応答内の全grid、最終盤面、level差分だけを使う。出力はseed×条件×Action群の集計で、game/level ID、盤面、trajectory、解答を含めない。
- dev基準実行を保存済みC2-003 seed別artifactのactions/levels/no-op/GAME_OVER/RESETとも照合する。

## 保持条件

- Action UCB/色UCB係数0.8、novelty +0.5、可視変化 +0.25、level進行 +4.0、Action候補/座標選択/乱数seed/80要求/RESETを固定する。唯一の変更要因は中間grid差分no-opへの罰免除。
- 通常candidate runtime、`接続/観測駆動探索Action.py`、HDS、Notebook、kernel version 4は変更しない。試験flagは評価コード内に閉じ、既定OFFとする。
- 環境/ゲーム/Action IDやhashで選択・分類を分岐しない。game識別はsplitの再現にだけ使い、個別情報を出力しない。
- dev以外の公開環境を評価しない。hidden評価や公式scoreを推定しない。

## 事前判定

試験条件が次をすべて満たす場合のみ、別指示で未使用holdout評価を検討する。

1. 各seedで完了levelを基準未満にしない。
2. 3 seed合計no-opを減らし、少なくとも2 seedで減る。
3. GAME_OVERをseed別に増やさない。HOLD・illegal Action・duplicate stepは基準と同様に0。
4. 15の全対比較で公開開始盤面と合法Action集合が一致。

不成立ならablationを不採用とし、candidate v4を維持する。条件を満たしてもruntime採用や公式改善とは呼ばない。holdoutは別工程として基準を固定して評価する。

## 成果物

匿名aggregate JSON、source hash、C2-003基準照合、targeted test/Ruff、seed×Action別previous/current/delta、採否を `検証/運転記録/ARC3-RUN-002_C1-005_中間Frame差分no-op罰ablation_20261023.md` に保存する。artifactは既存出力を上書きせず、候補bundle/kernelは更新しない。
