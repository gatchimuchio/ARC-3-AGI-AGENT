# ARC3-RUN-003 C2-040：GAME_OVER RESET後のAction/color UCB統計clear ablation

## 仮説と根拠

- 指示ID：`ARC3-RUN-003-C2-040`、正本v3.0。C1-014のread-only shadow監査で、同一初期公開条件のpost-reset選択が全legal既試行かつstats-clear shadowと5〜6/6回異なった。
- 仮説：GAME_OVER後RESETで新attemptへ移る時にAction番号別・ACTION6色別UCB統計だけをclearすると、no-opを減らすかlevels/WINを増やしつつGAME_OVERを増やさず再試行できる。
- C1-014は選択影響の証拠であって害の証拠ではない。このC2は因果的効果を別に評価する。C2-037/038/039の係数・seed・機構は再調整しない。

## 許可範囲・介入

- `検証/`配下に隔離policy subclass・paired runner・targeted testsだけを追加。共有policy、提出agent、HDS、candidate、Notebook/kernel、保護対象は変更しない。
- fixed dev split `20261022`の公開5環境、environment seeds `7/31/73`、各80 Action、GAME_OVER後SDK RESETを使用。保存trajectory再生なし。
- GAME_OVER観測でSDK RESETを選び、その次の`NOT_FINISHED`観測で最初のゲームActionを選ぶ直前に限り、Action番号別の回数/報酬合計/総作用数とACTION6色別の回数/報酬合計をclearする。盤面記憶、座標試行cache、RNG、探索係数、報酬式、合法gate、RESET手順は保持する。
- 出力はseed別aggregateのみ。初期盤面・個票・Action列は保存しない。

## 事前受入・採否

1. 各seedでpaired run 5/5の初期state・levels・legal Actions・公開盤面が一致する。
2. 各seedでlevels/WINは非減、GAME_OVER/no-opは非増。illegal/duplicate/HOLDは0、reset clear countは実際に完了したpost-reset decision数と一致する。
3. holdoutへ進むには全安全条件に加え、levels/WIN合計増加またはno-opが2 seeds以上で減り、残りseedで増えないこと。
4. 条件不成立なら棄却しholdout/C3へ進まない。PASSでもruntime採用は別C3/C4証拠を要する。

## 記録

- previous/current/delta、source/input/test/output SHA256、禁止key監査を追記記録へ保存する。
- Kaggle操作・公式score因果主張・共有policy/runtime変更は禁止。
