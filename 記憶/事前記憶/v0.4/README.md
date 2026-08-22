# ARC3 HDS事前記憶 v0.4

本ディレクトリはARC3公式サンプルをHDSで事前解析・実測・蒸留したPrior Memory正本である。

- 基底言語: 日本語
- 公式ゲーム: 25 / 25
- 公式レベル: 183 / 183
- 初期一手作用候補の実測: 5112 / 5112
- 再現確認済み成功trajectory: 9レベル
- HDSコンパイラ管轄: HDS

`183レベル_HDS索引.json` は全183レベルの作用集合・baseline_actions・盤面寸法・Sprite数を保持する。

`機構作用既知解_HDS正本.json` は25ゲームの機構索引、5112候補から得た作用実測集約、再現確認済み9成功trajectory、ARC2/3横断蒸留知識、HDS解析状態を統合する。

Action ID単独を意味として扱わず、対象role・relation・action・preconditionからstate deltaを読む。画面変化なしでもHidden Stateが変わる場合を保持する。

成功trajectoryはfresh instanceから再実行し、実際のlevel遷移を再現したものだけを既知解確定とする。