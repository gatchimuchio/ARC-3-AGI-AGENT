# C2-115 終端損失ペナルティのscreen

観測時刻: 2026-10-27T23:43:16Z
対照: C2-111のUCB/HDS方針、同じseedとローカル公開ゲーム開始状態
候補: 合法Actionが公開状態`GAME_OVER`を起こしたとき、そのActionの通常学習報酬を`-4.0`に置き換える。評価runner内だけの変更。

## 対応評価

| 指標 | 対照 | 候補 | 差 |
|---|---:|---:|---:|
| 対応開始状態 | 5 | 5 | 5/5一致 |
| 平均RHAE | 0.238095238 | 0.238095238 | 0 |
| 正/負/同点 | — | — | 0 / 0 / 5 |
| レベル差 | — | — | 0 |
| 勝利差 | — | — | 0 |
| Action数 | 400 | 400 | 0 |
| no-op数 | 9 | 17 | +8 |
| GAME_OVER回数 | 6 | 6 | 0 |
| 違法Action | — | 0 | — |
| 終端ペナルティ適用数 | — | 6 | — |

seed 7の5開始状態がすべて一致し、全ゲームのスコアが同点だった。事前宣言したscreen採択条件は平均RHAE差`+0.01`以上だが、実測差は`0`で、no-opが8増えた。**候補を棄却し、15組の拡張評価も昇格もしない。** 本番agent・HDS・Notebook・kernelは変更していない。KaggleのGPU枠・公式提出枠は消費していない。

## 証拠

- Runner: `検証/ARC3C2-115_terminal-loss-penalty-paired-evaluation.py` SHA-256 `2bef03cac31bb73e8ba953dcb4734df6da1f884d783b17414a7a569b74eb7557`
- Result: `運用/証拠/ARC26-UNIFIED/ARC3-C2-115-terminal-loss-penalty-result-20261027T234316Z.json` SHA-256 `5d15d29285fbe17e5048b47a246599af91245f010fd5a3afd45efcc0a6a5574f`
- Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-115-terminal-loss-penalty-screen-20261027T234316Z.json` SHA-256 `9e48a3f4bcb34f6b27ac2d58560bf77305b215593b4cbfe854d201b79d464cc3`

v6.0三点セットと保護対象を再確認し、現在の台帳と同じhashであることを確認した。
