# ARC3-RUN-003 C2-041：ACTION6同盤面・色報酬mean context ablation

## 仮説と根拠

- 指示ID：`ARC3-RUN-003-C2-041`、正本v3.0。C1-015で別色候補ありの同盤面・色再選択12件、結果カテゴリ一致12/12を観測。
- C2-038は離散Actionだけをstate-contextualizeし、ACTION6 color UCBを変更していない。C2-041はACTION6の同盤面・選択色の過去公開応答報酬meanだけをUCB exploitation項へ使う。
- 仮説：反復盤面で既知の色応答meanを参照し、未観測盤面/色ではglobal color rewardへfallbackすると、no-opを減らすかlevels/WINを増やし、GAME_OVERを増やさず探索できる。

## 許可範囲・介入

- `検証/`配下の隔離policy subclass・paired runner・targeted testsだけを追加。shared policy、提出agent、HDS、candidate、Notebook/kernel、保護対象は変更しない。
- fixed dev split `20261022`、公開5環境、environment seeds `7/31/73`、各80 Action、GAME_OVER後RESET有効。saved trajectory replayなし。
- ACTION6色選択時、現在公開盤面に同色の既応答があるときだけ、UCB reward meanを同盤面・色のmeanへ差替える。global UCB exploration bonus、Action番号UCB、座標試行cache、報酬定義、legal gate、RESETは保持。応答時はACTION6の公開報酬を同盤面・色bucketへ追記。
- 他のActionは完全に既定処理。出力はseed別aggregateのみ。

## 事前受入・採否

1. 各seedでprevious/current paired startが5/5一致。
2. 各seedでlevels/WINは非減、GAME_OVER/no-opは非増。illegal/duplicate/HOLDは0。
3. holdoutへ進むには全seed安全gateに加え、levels/WIN合計増加、またはno-opが2 seeds以上で減少し残りseedで増えないこと。
4. 不成立なら棄却しholdout/C3へ進まない。PASSでもruntime採用は別C3/C4証拠を要する。

## 記録

- previous/current/delta、source/input/test/output SHA256、禁止key監査を追記記録へ保存する。
- Kaggle操作・公式score因果主張・shared policy/runtime変更は禁止。
