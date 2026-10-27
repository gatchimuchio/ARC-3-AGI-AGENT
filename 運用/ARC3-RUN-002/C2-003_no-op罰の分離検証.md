# C2-003 指示書：no-op罰の分離検証

- 指示ID: `ARC3-RUN-002-C2-003`
- 版: 1.0／2026-10-23（JST）
- 対象: 観測駆動探索Actionの応答報酬におけるno-op罰
- 前回基準: C3-002 / `ARC3-SUBMIT-009`、探索報酬 `4.0*level + 0.5*novelty + 0.25*change - 0.5*no-op`

## 観測と仮説

C2-002は複数の報酬係数を同時に変え、dev seed 7/31/73でlevelは各1のまま、no-opは13/14/15から39/41/40へ増えた。作用別内訳ではACTION7が11回中10 no-opから50回中47 no-opへ、ACTION6のno-opは25から67へ増えた一方、ACTION6由来のlevel増分は3のまま。no-op罰を半減したことが不要作用を増やした可能性はあるが、他係数も同時変更だったため因果は未確定。

仮説: 他の係数をC3-002値に固定しno-op罰だけを`-0.5`から`-1.0`へ強めると、公開変化のない同一run内Actionが抑制され、レベル到達を維持したままno-opを減らせる。

## 目的

no-op罰一つだけの変更がAction効率に与える因果を、固定開発splitで分離検証する。結果が明瞭な場合のみ未使用holdoutへ固定適用する。

## 許可する範囲

- 探索報酬のno-op罰係数1つ。
- 作用別no-op数を集計する開発評価出力の最小追加（既存action responseから復元できる場合はコード追加しない）。
- 公開dev 5環境、action/environment seed 7/31/73でbefore/candidate比較。
- devで採用候補になった場合のみholdout 20環境、同seed 7/31/73でC3-002版と比較。

## 禁止と保持条件

- level進捗、new-board、visible-change係数は変更しない。
- ACTION ID、game/level ID、filename、hash、hidden state、trajectoryを根拠にruntime分岐しない。
- no-opを単に「悪い」と確定せず、合法性・同一観測の重複stepと区別して測定する。
- HDS HOLDを探索Action認可へ変換しない。SDK RESET、WIN、座標枯渇、80要求境界を維持。
- HDS v0.4.2、`AGENTS.md`、`制御/現在状態.json`、v2.0正本・履歴を変更しない。

## 検証

1. C3-002報酬係数でdev baseline seed 7/31/73を固定する。
2. no-op罰だけ`-1.0`にし、残りの係数・乱数seed・公開開始盤面・80要求予算を同じにしてdev比較する。
3. no-op総数およびAction別内訳、最大level、完了要求数、GAME_OVER/RESET、policy hold、WIN、illegal、duplicateを比較する。
4. dev全seedでlevel到達を維持し、no-opが再現性をもって減り、Action/合法性ゲートがPASSした場合だけholdoutへ進む。
5. holdoutでも最大levels completedをいずれも下回らず、no-opが減りillegal/duplicate増加がない場合のみ採用する。いずれか未達なら係数をC3-002へ戻し、不採用記録を残す。

## 終了条件

- no-op罰だけのbefore/current/deltaと作用別失敗署名を記録する。
- dev/holdout受入に失敗した場合は最新候補を維持し、次の故障へ進む。
- 採用時のみ新しい提出bundleを構築し、通常RunAll後に公式quota/期限を確認する。
