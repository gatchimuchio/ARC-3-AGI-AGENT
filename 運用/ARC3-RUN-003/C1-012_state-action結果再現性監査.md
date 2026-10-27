# ARC3-RUN-003 C1-012：同一公開盤面・Action結果カテゴリ再現性監査

## 選定根拠

- C1-011で固定dev 5環境×seeds 7/31/73の盤面再訪は34/45/44回と観測されたが、既知no-op離散Actionの合法な代替付き再選択は全seed合計1回だけで、単純なno-op回避は次のC2候補にならなかった。
- 現行UCB統計はAction番号単位で、同じ公開盤面で過去に実行した離散Actionの結果を次回選択へ分離していない。盤面再訪があるだけではstate-action memoryの根拠に足りないため、Action選択そのものが再訪時に起き、結果カテゴリが再現するかを先に監査する。

## 許可範囲

- `検証/`に隔離されたlive-run read-only evaluatorとtargeted testsだけを追加する。policy、agent、HDS、candidate、Notebook、保護ファイルは変更しない。
- C1-011と同一のfixed dev split seed `20261022`、5環境、seeds `7/31/73`、最大80 Action、GAME_OVER後RESET有効。保存Action列は再生しない。
- ACTION6は座標引数を伴うので対象外。ACTION1-5/7の`(公開盤面、Action番号)`を実行中だけ照合し、過去Actionの選択再発と公開結果カテゴリ（no-op / board-change / level-progress / terminal）だけを集計する。
- 次状態の盤面、座標、game/level ID、個別run、trajectory、正解は出力しない。盤面キーはプロセス内照合だけに使い、出力はseed別集計。

## C2候補の事前条件

- 15 run全体で、同一盤面・同一離散Actionの再選択が、他の合法離散Actionもある状態で10回以上、かつ3 seeds中2以上に分布すること。
- その繰返し選択後の公開結果カテゴリが前回と80%以上一致すること。標本が10未満、2 seeds未満、または結果一致率80%未満ならstate-action memoryは実装せずC1を閉じる。
- 条件を満たす場合も、この監査だけで採用しない。後続のC2は別指示書でprevious/current/deltaを事前固定する。

## 完了証拠

- 各seedのAction数・盤面再訪・known pair再選択・代替合法Action・結果カテゴリ一致/不一致、illegal/duplicate/HOLDを記録する。
- evaluator/test/source/input/output SHA256、匿名出力の禁止key監査、閾値採否、次工程を追記記録へ保存。
