# ARC3-RUN-002 C2-020 available_actions文脈識別可能性診断

- 実施日: 2026-10-23 JST
- 対象指示: [`C2-020指示書`](../../運用/ARC3-RUN-002/C2-020_available_actions文脈識別可能性診断.md)
- 判定: **文脈条件化仮説を棄却。runtime、candidate v4、Notebook/kernelは維持。**

## 方法とprevious照合

candidate v4既定方針を、split seed `20261022`のdev 5公開環境×Action seeds 7/31/73、各80要求、GAME_OVER後SDK RESETで再生した。`available_actions`、選択Action、直後の公開状態・level差分・no-opを作用応答時だけメモリ上で結合し、ゲームごとの記録は出力しなかった。

各seedで初期状態・初期合法Action集合・初期level数はC2-003基準の5/5一致。保存済みpreviousとcurrentは、全seedでactions、gameplay actions、RESET、GAME_OVER、levels、no-op、WIN、HOLD、illegal、duplicateの全指標が一致した。

| seed | Actions | gameplay / RESET | levels | no-op | GAME_OVER | WIN / HOLD / illegal / duplicate |
|---:|---:|---:|---:|---:|---:|---:|
| 7 | 400 | 394 / 6 | 1 | 9 | 6 | 0 / 0 / 0 / 0 |
| 31 | 400 | 394 / 6 | 1 | 9 | 6 | 0 / 0 / 0 / 0 |
| 73 | 400 | 394 / 6 | 1 | 17 | 6 | 0 / 0 / 0 / 0 |

## 観測結果と採否

- 15 runの1,182 gameplay応答に、全体では4種類の合法Action集合があった。各集合は複数seedに現れた。
- 各run内では合法集合が全Action中1種類のまま固定した。複数集合が出たrunは `0/15`、同一run内の集合遷移は `0`、最大種類数は1。
- 集合別に集約した応答率には差があるが、その集合はrun（ゲーム）間でしか変わらない。agentのUCB統計はrunごとに新規生成され、すでに現在の合法集合内だけから選択するため、この差は状態依存の追加学習信号ではない。集合を使うとゲーム間の違いを代理するに留まり、同一run内の文脈転移を示さない。
- 事前条件1（同一run内での集合変化）が不成立。Action別の文脈率差は条件付き実験へ進める根拠とせず、ablation・holdout評価を行わない。

## 検証と根拠

- 新規集計test: `2 passed`。Ruff check/format、compileall pass。`git diff --check`にwhitespace errorなし。既存CRLF正規化警告のみ。
- 最終匿名aggregate: `出力/ARC3-RUN-002-local/C2-020-available-actions-context-run2.json` SHA-256 `2477FC8F82C48CA1037AAB7E1FE7ADCC79666C9C7DA846759AFC7C8B43A93ED6`。
- 診断runner SHA-256 `DA146A5120D1E1484D48CEB18CEE4C3E4A314B277E835E27820C8BC6BE97140A`。test SHA-256 `C1BB650D475060CED727FC6AF2EDE14074AF7B955556533FABB1818616F1737A`。
- 対象方針 SHA-256 `325666ae54197474e33b4ff46306abc7ad12c7a489d2c2c3c59585d887e26510`。C2-003 dev previousとの指標deltaは全項目0。
- Kaggle再照会（2026-10-22 20:33 UTC）では`numToday=1`, `numTotal=4`。履歴の最新はbaseline `57527856`（COMPLETE、public `0.00`）で、candidate v4 Competition Rerunは未受理。既存quota watcher session `75984`は稼働中。

公式性能の改善は確認していない。C2-020は文脈仮説を不採用として閉じ、次の性能課題へ移る。
