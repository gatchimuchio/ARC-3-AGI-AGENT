# C1-007 指示書：複数Frameの境界保持read-only監査

- 指示ID: ARC3-RUN-002-C1-007
- 版: 1.0／2026-10-23（JST）
- 根拠: C5-001後続候補。C1-003/004でSDK応答に複数gridを確認したため、境界変換と既存Action/HDS入力までに途中Frameが落ちるかを確定する。

## 目的・範囲

公開SDK FrameData.frameからARC3境界の観測、HDS観測入力、探索Action応答記録まで、複数Frameが保持または意図的に最新盤面へ縮約される位置を読み取り専用で追跡する。C1-003の実SDK匿名集計を既存実測として照合し、現行unit testを実行する。

## 保持条件

- AGENTS.md、制御/現在状態.json、境界・agent・policy・HDS、candidate/Notebook/kernelを変更しない。
- 公開Frame列は集計/テスト以外に出力せず、ID、盤面、座標、色、trajectory、private/evaluator情報を保存しない。
- game/level ID分岐や新しいAction方針を追加しない。Kaggle実行なし。
- 境界が保持しているか、後段が明示的に最新gridのみを見るかを分けて判定する。保持を確認したら、Frame損失仮説は閉じる。

## 成果物

境界・HDS入力・探索Action各段の保持状態、既存C1-003実測、targeted test、各source SHA-256、採否をC1-007運転記録へ保存する。
