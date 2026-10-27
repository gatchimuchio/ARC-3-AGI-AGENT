# C2-014 指示書：GAME_OVER応答に対するUCB罰の単独評価

- 指示ID: `ARC3-RUN-002-C2-014`
- 版: 1.0／2026-10-23（JST）
- 根拠: C2-010 fixed holdout 60 runでGAME_OVER応答29件を観測。Action別ではACTION1–4各3、ACTION5が6、ACTION6が11、ACTION7が0。現行探索報酬はno-opへ`-1.0`を与える一方、level進行を伴わないGAME_OVERに追加罰を与えない。
- 仮説: level進行なしでGAME_OVERを起こしたActionのUCB報酬に`-1.0`を加えると、終端失敗Actionの再選択を減らせる。

## 比較

- previous: 候補v4相当の報酬。
- candidate: `GAME_OVER`かつ完了level増分が0以下の応答時に、対象Action報酬と（ACTION6なら）選択色報酬から各`1.0`を減算する。既存no-op罰と同じ大きさを使う。
- 公開観測・合法Actionだけを使用。80要求、SDK RESET、Action/色UCB、その他報酬と状態を固定。評価専用・既定OFF。runtime、HDS、Notebook、version 4は変更しない。

## 段階と採否

1. 固定dev 5環境×seed 7/31/73でprevious/candidateを比較し、previousをC2-003保存値へ照合。
2. dev必須条件: 全seedで完了levelを維持、GAME_OVER合計が減少し2 seed以上で減少、seed別GAME_OVER非増加、no-opはseed別・合計とも非増加、HOLD/illegal/duplicateは0、開始観測が全対で一致。
3. 全条件を満たす場合のみfixed holdout 20環境×seed 7/31/73へ進む。同じ条件を保ったうえ、GAME_OVER削減を再現する。
4. 不合格ならholdoutとruntime変更を行わずcandidate version 4を維持する。

## 成果物

- 匿名seed×condition aggregate、Action別GAME_OVER数、previous/current/delta、baseline/開始一致、全gate、holdout可否、tests、source/output SHA-256、採否を `検証/運転記録/ARC3-RUN-002_C2-014_GAME_OVER報酬評価_20261023.md` に保存する。
- game/level ID、filename、hash、答え、hidden/evaluator state、trajectory lookupを使わない。ローカル結果を公式scoreの証拠へ外挿しない。
