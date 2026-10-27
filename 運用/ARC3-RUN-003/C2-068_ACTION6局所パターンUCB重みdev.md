# C2-068 — ACTION6局所パターンpriorのUCB重みablation

## 問い

C2-067の事前gate `+0.01`に対し、UCB weight `0.35`はRHAE差`+0.004360858`（改善1・後退0・同点14）までだった。観測済み局所特徴を活用しつつ、未知特徴への探索bonusだけを`0.35→0.0`にして同一devで試す。

## 固定条件

- C2-067と同じsplit、train/dev公開game集合、seeds `7,31,73`、同じ40/80 Action予算、policy/seed、特徴と報酬。
- 変更するのは局所特徴memoryのUCB bonus weightだけ。train/devを各episodeで分離し、dev間でmemoryを混ぜない。
- paired開始状態、Action trace変化、RHAE、level/WIN/no-op、illegal/duplicate/errorを記録。
- gateは平均ΔRHAE `>=+0.01`、score improvement数がregression数以上、level/WIN合計を減らさず、全開始条件一致、illegal/duplicate/error 0。

## 採否

gate未達ならC2-067の小差を正式改善とせず、残り15ゲームholdout・runtime接続・Kaggle提出へ進まない。通過時のみ未見15ゲームholdoutを同条件で評価する。
