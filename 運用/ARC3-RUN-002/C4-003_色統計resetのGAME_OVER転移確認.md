# C4-003 指示書：色統計resetによるGAME_OVER減少のholdout確認

- 指示ID: `ARC3-RUN-002-C4-003`
- 版: 1.0／2026-10-23（JST）
- 根拠: C4-002 devでは、色UCB統計だけをlevel進行時にresetした候補の完了levelは3/3 seedで維持され、no-opは全seed同数だった。一方GAME_OVERは2/3 seedで1件ずつ減少した。C4-002のno-op条件は不合格として閉じたまま、この別の終端失敗低下信号を既存固定holdoutで検証する。
- 仮説: levelをまたいで色UCB成績を持ち越さない方針は、Action効率を悪化させずGAME_OVERを再現性をもって減らす。

## 比較と必須条件

- previous: 現行candidate v4相当。candidate: C4-002と同一で、正のlevel進行時に色UCB回数・報酬だけをreset。
- 固定holdout 20公開環境×seed 7/31/73、最大80要求、GAME_OVER後SDK RESETで比較する。実験中にコード・閾値を調整しない。
- previousはC2-003保存済みholdout各seedの全基準集計と一致し、全60対で公開開始状態が一致すること。
- 各seedで完了levelを維持、no-opを増やさず、GAME_OVERを増やさない。合計GAME_OVERを2件以上減らし、3 seed中2 seed以上で減少すること。
- HOLD・illegal・duplicateは全て0。これらのいずれかを満たさなければcandidateを棄却する。

## 保持・成果物

- 新しい本番runtime動作は追加しない。C4-002の既定OFF評価ablationのみ利用する。
- 保存するのは匿名seed×condition aggregateと開始一致数だけ。game/level ID、座標、盤面、hidden/evaluator stateは出力しない。
- C4-002 dev signal、固定holdout結果、baseline一致、各seed previous/current/delta、全ゲート、test/source/output SHA-256、採否を `検証/運転記録/ARC3-RUN-002_C4-003_色統計resetGAME_OVER転移確認_20261023.md` に記録する。
- PASSでも公式score改善とは呼ばない。PASS時は次のC6横断回帰と提出候補審査へ送り、不合格ならC4-002の観測を局所的なGAME_OVER低下仮説として留める。
