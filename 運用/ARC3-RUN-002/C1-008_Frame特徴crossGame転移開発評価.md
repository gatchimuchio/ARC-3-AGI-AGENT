# C1-008 指示書：Frame特徴のcross-game転移開発評価

- 指示ID: ARC3-RUN-002-C1-008
- 版: 1.1／2026-10-23（JST）
- 根拠: C1-006で直前Frame特徴は同一環境内のHDS予測coverageを増やしたが、共通coverage上の正答はAction-only HDSと同一。異なるゲームへ移る価値は未確認。

## 目的・対象

C1-006で事前固定したAction番号と直前Frame由来3真偽特徴を変えず、固定dev 5公開環境にleave-one-environment-outを適用する。毎foldで4環境だけを学習し、未学習の1環境だけをread-only評価する。Action-only HDSと訓練4環境のAction別多数派を同一テスト行で比較する。

## 方法・保持条件

- split seed 20261022、environment seed 31、policy seed 7/31/73、各80要求。初期公開状態一致を確認する。
- 各policy seedごとに環境別HDS応答サンプルを収集後、5 foldを実施。HDSにはgame/level ID・GUID・盤面・座標・色・trajectoryを渡さず、fold内の環境境界情報も入力へ含めない。
- HDS計算量を有限に保つため、各訓練環境からeligible時系列サンプルを最大15件、列の全体に均等配置して固定抽出する。各foldの訓練上限は60件。対象環境はeligible全件を評価する。Action別多数派も同じ抽出訓練行を使う。
- 結果は可視変化、level進行、新規盤面。対象環境のどの結果も学習に使わない。
- 出力はpolicy seed別aggregateに限定し、fold別行、環境名、サンプル・予測値を保存しない。hidden/evaluator情報、Kaggle実行はなし。
- 成功条件は、Frame HDSとAction-only HDS・Action別多数派の三者共通coverageが30件以上あり、Frame HDSが同一集合上の双方を上回り、かつ3 policy seed中2 seed以上でdeltaが正、残るseedでも負にならないこと。条件を満たさなければ転移改善は未成立とし、holdout/runtimeへ進まない。
- 提出runtime、HDS core、方針、Notebook/kernel、candidate bundle、保護対象は変更しない。
- 全訓練行を用いた初回実行は25分経過後もartifact作成前だったため中断。出力を保存せず、下記固定サンプル上限で再実行する。中断実行の一部結果は採否に使わない。

## 成果物

再利用評価器/targeted tests、匿名aggregate、source/input SHA、coverage/正答のprevious/current/delta、受入判定をC1-008運転記録へ保存する。
