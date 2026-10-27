# C2-020 指示書：available_actions文脈の識別可能性診断

- 指示ID: `ARC3-RUN-002-C2-020`
- 版: 1.0／2026-10-23（JST）
- 対象: candidate v4既定方針のAction別報酬集計と公開合法Action文脈
- 前回基準: C2-003 dev 5公開環境×seed 7/31/73、80要求、GAME_OVER後RESET

## 根拠と仮説

現行方針はAction番号ごとの報酬を同一run内で全公開状態にわたり集計する。C2-019までの公開診断ではno-op、Action6座標特徴、GAME_OVER等を検討したが、runtimeに追加できる状態依存規則は得られていない。公開`available_actions`集合が状態により反復して変わり、同じActionの応答品質がその文脈で再現可能に異なるなら、合法集合を状態文脈とする汎用Action別統計を別実験で検討できる。

## 目的

開発splitだけを同一条件で再生し、各Action選択直前の公開`available_actions`集合と直後の公開応答を匿名集計する。合法集合文脈の変化・反復・Action別応答差に、次の一要因評価を正当化できるだけの支持があるか判定する。

## 許可する範囲

- split seed `20261022`の開発5環境、Action seeds 7/31/73、各環境80要求、GAME_OVER後SDK RESETを使用する。
- candidate v4と同じpolicy・係数・選択乱数・環境seedを使い、変更前のC2-003 dev aggregateとactions/levels/no-op/GAME_OVER/RESET/WIN/HOLD/illegal/duplicateを照合する。
- 作用直前の合法Action集合、選択Action、直後のstate・level増分・盤面変化/no-opだけをメモリ上で結合し、集合signature×Action×seedの匿名件数へ集約する。同一Agent run内で合法集合が変化する回数も集計する。
- 生のgame/level ID、盤面、座標、guid、trajectory、signature別小標本の個票は出力しない。診断runnerと匿名aggregateを新規に保存し、再実行用の任意`--output`を備える。

## 禁止と保持条件

- runtime policy、agent、HDS、Notebook、Kaggle kernel/version 4、holdoutを変更・再実行しない。
- game/level IDやhashを行動選択・分類条件へ使わない。hidden/evaluator情報を参照しない。
- この診断を能力改善や公式score予測として扱わない。
- `AGENTS.md`、`制御/現在状態.json`、`運用/ARC3文書正本.md`、v2.0正本・v1.0履歴を変更しない。

## 事前判定

合法集合を文脈にした次のablationを検討できるのは、次の全条件を満たす場合だけとする。

1. 異なる合法集合が同一Agent run内で変化し、その変化が2つ以上のrunで観測される。run間の違いだけでは条件成立としない。
2. 同一run内の複数集合に同じActionが各20件以上現れ、その条件が2つ以上のrun・2 seed以上で再現する。集合間のno-opまたはGAME_OVER率差の向きも、比較可能seedの3分の2以上で一致する。
3. previousとの全基準指標照合が完全一致し、HOLD・illegal・duplicateが0。

満たさない場合は文脈統計仮説を不採用とし、candidate v4を維持する。満たした場合もruntimeへ採用せず、dev限定の独立ablation指示書を作ってからholdout転移評価を別工程で行う。

## 成果物と終了条件

匿名aggregate、runner source hash、targeted test、Ruff/compileall、基準照合、条件別previous/current/delta、採否と次課題を `検証/運転記録/ARC3-RUN-002_C2-020_available_actions文脈識別可能性診断_20261023.md` に保存する。C2-020は診断の再現と事前判定の実施をもって閉じる。
