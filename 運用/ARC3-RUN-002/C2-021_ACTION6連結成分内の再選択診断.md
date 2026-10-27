# C2-021 指示書：ACTION6連結成分内の再選択診断

- 指示ID: `ARC3-RUN-002-C2-021`
- 版: 1.0／2026-10-23（JST）
- 対象: candidate v4既定方針のACTION6座標選択
- 前回基準: C2-003 dev 5公開環境×seed 7/31/73、80要求、GAME_OVER後RESET

## 根拠と仮説

現行方針は盤面内の未試行セルから、UCBで選んだ可視色の座標を選ぶ。記憶は完全一致盤面内の座標単位で、同一4近傍・同色成分の別セルを別対象として扱う。成分内で複数座標を試しても最終盤面・levelが変化しない事例が反復するなら、未試行セルより未試行成分を選ぶ汎用方針を一要因評価できる。

## 目的

devだけでACTION6の作用前盤面を4近傍・同色の連結成分へ一時分割し、同一run・同一盤面・同一level文脈で同じ成分が再選択された頻度と直後応答を匿名集計する。連結性は診断特徴であり、ゲーム上のobject意味を断定しない。

## 許可する範囲

- split seed `20261022`のdev 5環境、Action seeds 7/31/73、各80要求、GAME_OVER後SDK RESETを使用する。
- 作用前の公開最新盤面とACTION6座標から4近傍・同色成分だけを計算する。色値、座標、盤面、component maskはメモリ内だけで処理する。
- 成分面積bucket、初回／同一成分再選択、no-op・level進行・GAME_OVERの匿名件数をseed別・全体で集計する。小標本bucketは出力から抑制する。
- C2-003 dev previousとactions/levels/no-op/GAME_OVER/RESET/WIN/HOLD/illegal/duplicateを照合する。診断runner・targeted test・匿名aggregateを新規作成する。

## 禁止と保持条件

- runtime policy、agent、HDS、Notebook、Kaggle kernel/version 4、holdoutを変更・再実行しない。
- game/level ID、hash、scorecard、evaluator内部、hidden state、非公開正解を参照しない。IDで分類せず、問題固有scriptや答え対応表を作らない。
- board、座標、成分形状、色値、trajectory、run個票を保存しない。成分をゲーム上のobject、click target、原因と断定しない。
- `AGENTS.md`、`制御/現在状態.json`、`運用/ARC3文書正本.md`、v2.0正本・v1.0履歴を変更しない。

## 事前判定

「同一盤面・同一level文脈での再選択」を避ける開発ablationへ進めるのは、次の全条件を満たす場合だけとする。

1. 連結成分再選択が20件以上あり、2 seed以上に現れる。
2. 再選択のno-op率が成分初回選択より10 percentage points以上高く、その差の向きが比較可能seedの3分の2以上で一致する。
3. 再選択にlevel進行がある場合、その進行が初回選択を含む同じ成分全体の応答を上回らず、GAME_OVER・HOLD・illegal・duplicateも悪化しない。
4. previousの基準指標と初期状態metadataが全seedで一致する。

条件不成立ならcomponent単位の再選択回避を棄却し、candidate v4を維持する。成立してもruntimeへ直接採用せず、別指示書のdev-only ablationを先に行う。

## 成果物と終了条件

匿名aggregate、runner/test source hash、targeted test、Ruff/compileall、previous/current/delta、bucket抑制条件、採否を `検証/運転記録/ARC3-RUN-002_C2-021_ACTION6連結成分内再選択診断_20261023.md` に保存する。診断実行と事前判定をもってC2-021を閉じる。
