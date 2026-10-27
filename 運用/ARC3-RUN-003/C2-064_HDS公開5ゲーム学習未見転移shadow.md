# ARC3-RUN-003 C2-064：HDS公開5ゲーム学習・未見1ゲーム転移shadow

## 仮説と優先順位

- v6は「記憶→推論→結果観測→適応→未見対象への効果」の実測を要求する。旧C2-036の環境間HDS状態分離shadowだけではこの転移効果を測れないため、本件はOwnerが採用したv6の直接指示を優先し、公開情報のみを使う限定したID-free転移試験とする。
- 先行2ゲーム×40手のHDS学習は、一つの未見ゲームで候補差がなく、別の粗い文脈試験では2回だけguided choiceが起きたがscore/level差はなかった。公開学習量を5ゲームへ増やすと、未見候補またはscoreに差が出るかを測る。

## 固定条件

- fixed split seed `20261022`の公開25環境から先頭5件を学習用、未学習残り20件から先頭1件をholdoutとする。保存trajectory再生なし。
- 学習は各40 Action上限、environment seeds `31..35`。HDS照会は学習中に無効化して従来policyと同じAction選択を保ち、公開応答からのHDS更新だけを行う。
- 5環境で一つのHDSを維持するが、入力は汎用公開状態3特徴・Action番号・公開応答区分だけ。game/level ID、board内容、座標、色値、Action列はHDSへ渡さない。
- 未見1環境で同じseed `20261027`・40 Action上限のbaseline/HDS-guided shadowを比較。候補は合法Actionの順位へだけ使い、HDSの実行認可はfalseのまま。

## 採否gateと制限

- HDS更新件数、学習時間、active rule数、holdout candidate/prediction/guided数、RHAE・level・WIN・no-op差を保存する。
- 未見1環境のscore改善、level/WIN非減、legal/duplicate/HOLDの各0をすべて満たす場合だけ、別指示で複数holdoutへの拡張を検討する。満たさない場合は転移効果を支持せず終了する。
- この1環境shadowだけでは一般化・競技score改善・公式改善を主張しない。Notebook/kernel/Kaggle/公式quota/共有runtimeは変更・使用しない。
