# C2-013 指示書：ACTION6同色近傍あり座標の単独評価

- 指示ID: `ARC3-RUN-002-C2-013`
- 版: 1.0／2026-10-23（JST）
- 根拠: C2-011 dev ACTION6 703応答のうち、選択セルに同色4近傍が0件の132応答ではlevel進行0件だった。進行3件はいずれも同色近傍1件以上（bucket `1_2` が2件、`3_4` が1件）だった。事例は3件だけなので仮説に限定し、一要因で検証する。
- 仮説: 同色の隣接関係をもつセルは、孤立セルよりlevel進行へ寄与しやすい。

## 比較

- previous: 候補v4の色UCBで選んだ色の未試行セルから一様抽選。
- candidate: 同色4近傍が1件以上ある同色未試行セルが存在する場合、その集合から一様抽選。候補が尽きた、または存在しない場合は従来の全未試行集合から抽選。
- 色選択UCB、Action UCB、報酬、乱数seed、80要求、SDK RESET、他の状態を固定。ACTION6座標選択の局所規則だけを変更する。

## 段階と採否

1. split seed `20261022` のdev 5環境×seed 7/31/73で比較。previousはC2-003保存値、公開初期盤面・状態・合法Actionへ照合する。
2. dev必須条件は、全seedで完了levelを下回らない、no-op合計を減らす、少なくとも2 seedでno-op減少、GAME_OVERをseed別に増やさない、HOLD/illegal/duplicateを0に保つこと。
3. 全条件を満たす場合だけ固定holdout 20環境×seed 7/31/73で検証する。holdoutはlevel/no-opをseed別に悪化させず、no-op合計を減らし、GAME_OVER/HOLD/illegal/duplicateを増やさないこと。
4. 不合格時はholdout・runtime変更を行わず、candidate version 4を維持する。

## 保持条件と成果物

- game/level ID、filename、hash、答え、hidden/evaluator state、trajectory lookupを選択に使わない。公開盤面・色・合法Actionだけを使い、選択色内の全未試行セルを維持する。
- 評価専用・既定OFFの方針と匿名aggregateを保存し、既存artifactを上書きしない。
- previous/current/delta、baseline/開始一致、Action6近傍bucket、ゲート、holdout可否、test、source/output SHA-256、採否を `検証/運転記録/ARC3-RUN-002_C2-013_ACTION6同色近傍評価_20261023.md` に記録する。
