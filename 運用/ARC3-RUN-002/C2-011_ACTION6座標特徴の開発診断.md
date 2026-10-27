# C2-011 指示書：ACTION6座標の公開特徴診断

- 指示ID: `ARC3-RUN-002-C2-011`
- 版: 1.0／2026-10-23（JST）
- 根拠: C2-010のholdout 60 runではlevel進行5件すべてACTION6後、同ACTIONは1,183回中278回no-op。保存済み記録にはクリック前盤面と選択座標の対応特徴がなく、選択可能な規則を検討できなかった。C1-005では中間Frame差分no-op罰の免除はdev受入を通らなかった。

## 目的

現行候補の座標選択を変えず、ACTION6を選んだ公開盤面の汎用特徴と応答結果がdevで関連するか測る。関係が乏しければ追加の座標規則を作らず、現在の選択を維持する。

## 対象と測定

- 固定dev split先頭5公開環境、seed 7/31/73、現行v4相当policy、80要求、GAME_OVER後SDK RESET。各条件をC2-003 dev seed artifactと照合。
- 実際に選ばれたACTION6座標について、盤面上の選択色の相対頻度、上下左右の同色隣接数、盤面内の相対中心距離だけを事前定義featureとして記録する。
- 各feature bucketをno-op／盤面変化／level進行に対して集計し、seed別反復とサンプル数を示す。個別盤面・色ID・座標・game/level ID・trajectoryは出力しない。
- featureは観察・集計にだけ使い、Action選択、報酬、分岐へ接続しない。

## 保持条件

- policy/runtime、HDS、candidate bundle、Kaggle kernelを変更しない。計測monkeypatchは呼出順・戻り値・状態を変更しない。
- game/level ID、filename、hash、hidden state、answer、評価器内部情報を選択・分類・特徴に使わない。
- devのみを使用し、holdoutへ拡張しない。相関を因果・予測力・能力改善と表現しない。
- `AGENTS.md`、`制御/現在状態.json`、正本ポインタ、v2.0/v1.0原文を変更しない。

## 判定

あるfeature bucketが複数seedに十分な成功件数を持ち、盤面変化/no-op双方に対して一貫した分離がdev内で再現しない限り、汎用選択規則の候補にしない。進行数が少ない、結果がseed依存、単一bucketに偏る場合は「判定不能／候補なし」とする。採用候補が見つかった場合でも、別指示書の一要因変更・dev比較・受入後の未使用holdout検証を必須とする。

## 成果物

匿名feature×outcome集計JSON、baseline一致、runner/test/source SHA、サンプル限界、採否を `検証/運転記録/ARC3-RUN-002_C2-011_ACTION6座標特徴診断_20261023.md` に保存する。既存出力を上書きしない。
