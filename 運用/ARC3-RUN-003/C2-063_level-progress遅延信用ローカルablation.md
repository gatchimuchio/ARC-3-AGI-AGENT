# ARC3-RUN-003 C2-063：level進行報酬の遅延信用評価

## 仮説

現行policyはlevel進行したActionだけに`+4.0`を計上する。level進行へつながる直前の探索Actionも、同一run・同一level内の最近4手へ限定して弱く信用配分すれば、後続選択が改善する可能性がある。

## 固定条件・介入

- fixed dev split seed `20261022`、公開5環境、environment/policy seeds `7/31/73`、最大80 request、GAME_OVER後SDK RESET有効。
- previousは現行policyそのまま。candidateはlevel進行時に限り、現在Actionへ既定どおり報酬を計上した後、同一level内の直前最大4 Actionへ合計`2.0`（level進行報酬4.0の半分）を、直近から重み`1, 0.5, 0.25, 0.125`に比例配分する。Action UCB/色UCBの既存回数は変えず、既存報酬合計へ追加する。
- level進行/GAME_OVER/WINで履歴を消去。RESETをまたがない。candidateは直近4手、公開level進行だけを使い、game/level ID・座標hash・軌跡を参照しない。
- 探索Action policyの隔離subclassだけで評価。HDS、shared runtime、提出agent、Notebook/kernel、Kaggle、公式quotaは変更・使用しない。

## 採否gate

1. previous/candidateは初期公開state・level・legal Actions・boardが全15対一致する。
2. level進行/終端までの介入前action/response prefixは一致し、illegal/duplicate/scorecard contract errorは0。
3. candidateの平均RHAE差が正、level総数が非減、paired score regressionが0の場合のみholdout 20環境へ進む。不成立なら棄却しholdout/runtimeへ進まない。
4. 公開RHAE以外の学習成立・公式score改善は主張しない。
