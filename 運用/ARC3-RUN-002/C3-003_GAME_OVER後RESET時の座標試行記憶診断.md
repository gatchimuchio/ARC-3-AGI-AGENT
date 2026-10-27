# C3-003 指示書：GAME_OVER後RESET時の座標試行記憶診断

- 指示ID: `ARC3-RUN-002-C3-003`
- 版: 1.0／2026-10-23（JST）
- 対象: candidate v4既定方針のACTION6座標試行記憶
- 前回基準: C2-003 dev 5公開環境×seed 7/31/73、80要求、GAME_OVER後SDK RESET

## 根拠と仮説

現行探索方針は完全一致盤面ごとのACTION6試行座標を同一Agent内で保持する。GAME_OVER後はSDK RESETで探索を継続し、方針の座標cacheも保持する。reset後に同じ公開盤面へ戻る場合、既試行座標が未試行候補を過度に減らして探索幅や進行機会を狭める可能性がある。逆に、前回の失敗座標を避ける有効な記憶の可能性もある。

## 目的

candidate v4を変更せず、公開dev 5環境×Action seeds 7/31/73で、GAME_OVER→SDK RESET直後の最初のNOT_FINISHED盤面が同一run内の既試行盤面と一致する頻度、およびその盤面の既試行座標割合を測る。検出に使う盤面・座標・cache内容は実行中のメモリだけに保持し、匿名集計だけを保存する。

## 許可範囲と保持条件

- split seed `20261022`、各80要求、`retry_game_over=True`で既定policyを15 run実行する。
- 現在の公開盤面を完全一致比較にだけ使い、保存済み`_座標試行`の件数と盤面セル数の割合を算出する。盤面値・shape・hash・座標・run個票は保存しない。
- C2-003 dev previousの初期state・合法Action集合・完了level metadataと、actions/levels/no-op/GAME_OVER/RESET/WIN/HOLD/illegal/duplicateを照合する。
- 診断runner、targeted test、匿名aggregate、運転記録を作成する。
- runtime policy、agent、HDS、Notebook、kernel/version 4、holdoutは変更・再実行しない。
- `AGENTS.md`、`制御/現在状態.json`、`運用/ARC3文書正本.md`、v2.0正本、v1.0履歴を変更しない。

## 事前判定

reset後の座標cacheをclearするdev-only ablationへ進む条件はすべて満たすこと。

1. reset後に既試行盤面へ戻る事例が10件以上、2 seed以上に現れる。
2. cache-hit事例の既試行座標割合の中央値が20%以上。
3. previous基準指標と初期metadataが全seedで一致する。

条件不成立ならcache reset仮説を棄却し、candidate v4を維持する。成立してもruntimeへ直接採用せず、別の限定指示書によるdev-only ablationを先に行う。

## 禁止

- game/level ID、filename、hash、scorecard、evaluator internals、hidden state、非公開正解を参照しない。game/level IDで分類・行動分岐しない。
- board、座標、色、shape、cache event行、trajectory、個別ゲーム結果を保存しない。
- cache-hitの関連だけで、GAME_OVER後にcacheを消す因果的改善を主張しない。

## 成果物と終了条件

匿名aggregate、runner/test source hash、targeted test、Ruff/compileall、previous/current/delta、採否を `検証/運転記録/ARC3-RUN-002_C3-003_GAME_OVER後RESET座標記憶診断_20261023.md` に保存する。診断実行と事前判定をもってC3-003を閉じる。
