# ARC3-RUN-003 C1-015：同一盤面・ACTION6色の結果再現性監査

## 選定根拠

- C2-038は同一盤面の離散Action 1-5/7だけを対象にし、ACTION6の色UCBは既定のまま残した。C1-012も座標引数を持つACTION6を除外している。
- 現行policyは選択色の報酬を公開盤面文脈から分けず全盤面で集約する。同一盤面で同色Action6を別座標に再選択した際、公開結果カテゴリが再現するかを未監査。カテゴリ再現が不十分ならstate-color統計の候補を作らない。

## 許可範囲

- `検証/`配下のlive-run read-only evaluator・targeted testsだけを追加する。shared policy、agent、HDS、candidate、Notebook/kernel、保護対象は変更しない。
- fixed dev split `20261022`、公開5環境、environment seeds `7/31/73`、各最大80 Action、GAME_OVER後RESET有効。保存Action列は再生しない。
- 同一run内で`(公開盤面, 選択ACTION6色)`だけをメモリ内照合する。同じ組の結果カテゴリを`no_op / board_change / level_progress / terminal`で比較する。再選択時に未試行座標が残る別色を選べる機会も数える。
- 出力はseed別aggregateのみ。盤面、色値、座標、Action列、個別run、game/level IDは保存しない。

## C2候補の事前条件

- 同一盤面・色の再選択で別色も合法候補に残る機会が全体10件以上、3 seeds中2以上に分布する。
- その繰返し応答の公開結果カテゴリ一致率が80%以上。
- 標本条件未達または一致率未達ならstate-color reward contextualizationのC2を作らずC1を閉じる。支持されても因果的改善は主張せず、別C2 paired ablationを要する。

## 完了証拠

- seed別ACTION6選択数、同盤面・同色の繰返し、別色候補の有無、結果カテゴリ一致/不一致、illegal/duplicate/HOLD、Action/level/no-op/GAME_OVERを記録する。
- source/input/test/output SHA256、禁止key監査、閾値採否を追記記録へ保存する。
- Kaggle操作、公式score因果主張、runtime採用は禁止。
