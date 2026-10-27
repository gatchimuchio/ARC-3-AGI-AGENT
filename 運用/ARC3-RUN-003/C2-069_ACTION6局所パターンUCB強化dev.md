# C2-069 — ACTION6局所パターンUCB探索強度dev

## 問い

C2-067のweight `0.35`は平均ΔRHAE`+0.004360858`、C2-068のweight `0.0`は`-0.031149144`。局所featureのposterior meanへの過剰固定を避けるweight `0.7`が未見devで、事前gateを超えるかを測る。

## 固定条件

- split seed、train/dev公開集合、train 5×40、dev 5×seeds `7,31,73`×80 Action、他のコード・memory prior・報酬はC2-067と同じ。
- 変更はfeature-UCB weight `0.35→0.7`だけ。
- gateは平均ΔRHAE `>=+0.01`、score improvement数がregression数以上、level/WIN合計を減らさず、開始状態一致、illegal/duplicate/errorが0。

## 採否

gate未達ならC2-067の小差も未確認改善として扱い、ACTION6局所学習をruntime/Notebookに接続せず残り15ゲームholdoutへ進まない。gate達成時のみ別holdoutを実施する。
