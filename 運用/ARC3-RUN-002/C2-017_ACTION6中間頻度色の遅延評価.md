# C2-017 指示書：ACTION6中間頻度色の遅延評価

- 指示ID: `ARC3-RUN-002-C2-017`
- 版: 1.0／2026-10-23（JST）
- 根拠: C2-015 devで選択色frequency bucket「middle_10_to_50pct」はACTION6 48回、GAME_OVER 3回、level進行0回だった（seed別GO 1/2/0）。小標本の候補信号であり、原因や別環境への転移は未確認。
- 目的: 他bucketの未試行色がある場合だけmiddle色を遅延し、同一条件のdev/holdoutで進行・GAME_OVER・no-opへの影響を測る。

## 方法

- 固定split seed 20261022、dev 5公開環境×seed 7/31/73、最大80要求、GAME_OVER後SDK RESETでC2-003 previousと一要因candidateを比較する。
- candidateはACTION6の現在盤面で未試行座標を持つ色だけを対象にし、dominant（同率最多を含む）またはrare（頻度10%未満）が一色以上ある間はmiddle（10%以上・最多以外）を選択候補から外す。該当色がなければ既存選択へfallbackする。
- 色ID・game/level ID・盤面hashでは分岐しない。UCB式、報酬、Action順、座標選択、HDS、SDK/runtime経路は変更しない。
- 匿名aggregateのみを出力し、baseline、開始状態、合法Action、HOLD、illegal、duplicateを確認する。

## 採否条件

- dev: 3 seedすべてでlevelを維持し、no-opをseed別に増やさず合計減少、2 seed以上で減少。GAME_OVERはseed別に増やさず合計減少。HOLD/illegal/duplicateは0、開始状態は全対一致。
- devを通過した場合だけ未使用holdout 20環境×同じ3 seedへ進む。holdoutでは各seedのlevel/no-op/GAME_OVERを悪化させず、合計GAME_OVERを減らし、HOLD/illegal/duplicateを0に保つこと。
- いずれか不合格なら不採用とし、runtime/candidate v4を維持する。PASSしても公式評価前に公式score改善を主張しない。

## 成果物

- previous/current/delta、dev/holdout gate、匿名aggregate、tests、source/output SHA-256、採否を `検証/運転記録/ARC3-RUN-002_C2-017_ACTION6中間頻度色評価_20261023.md` に記録する。
