# ARC3-RUN-002 C6-002 candidate v4 run-seed安定性診断

- 実施日: 2026-10-23 JST
- 指示: [`C6-002指示書`](../../運用/ARC3-RUN-002/C6-002_candidatev4乱数seed安定性診断.md)
- 判定: **追加7 seedを含む10 run seedを測定。完了levelに1〜4の変動があり、WINは全seedで0。runtime・candidate sourceは変更なし。**

## 方法とseedの意味

- 固定split seed `20261022`、公開holdout 20環境、各policy最大80 Action、GAME_OVER後SDK RESET。既存seed 7/31/73はC6-001のC6合格出力から再利用し、新規seed 11/17/29/43/59/83/101を同じevaluation runnerで追加した。
- evaluatorの`--seed`は`LocalEnvironmentWrapper`、探索policyの`random.Random(seed)`、random baseline RNGのすべてに渡る。したがって本結果は環境とpolicyを合わせたrun-seed感度であり、policy RNGだけの効果を分離しない。
- 新規7 seedは各20/20 runでrandom/explorationの初期公開盤面・合法Action集合が一致。全条件でAction上限・splitを固定し、game IDやlevel IDによるruntime分岐はない。

## candidate v4 exploration集計

各seedはholdout 20 run、探索policy合計1,600 Action要求。

| run seed | 完了level | WIN | no-op | GAME_OVER | RESET |
|---:|---:|---:|---:|---:|---:|
| 7 | 1 | 0 | 150 | 10 | 10 |
| 31 | 2 | 0 | 128 | 9 | 9 |
| 73 | 2 | 0 | 137 | 10 | 10 |
| 11 | 3 | 0 | 119 | 9 | 8 |
| 17 | 3 | 0 | 123 | 9 | 9 |
| 29 | 4 | 0 | 169 | 11 | 11 |
| 43 | 3 | 0 | 137 | 8 | 8 |
| 59 | 3 | 0 | 130 | 10 | 10 |
| 83 | 3 | 0 | 119 | 11 | 11 |
| 101 | 3 | 0 | 118 | 9 | 9 |
| 合計／中央値 | 27 / 3 | 0 / 0 | 1,330 / 129 | 96 / 9.5 | 95 / 9.5 |

完了levelは範囲1〜4、中央値3、平均2.7。WINは10/10 run seedで0。総Actionは全条件16,000、no-op範囲118〜169、GAME_OVER範囲8〜11。policy HOLD、illegal Action、重複観測stepは全条件0。

## 同seed random baseline（追加7 seed）

| 指標 | Random | Exploration | Exploration - Random |
|---|---:|---:|---:|
| completed levels | 5 | 22 | +17 |
| WIN | 0 | 0 | 0 |
| Actions | 11,200 | 11,200 | 0 |
| no-op | 2,394 | 915 | -1,479 |
| GAME_OVER | 53 | 67 | +14 |

同一seed・同一holdout開始状態に対して、探索policyはlevel数を多く記録しno-opが少なかった一方、GAME_OVERは14件多かった。これは公開holdout上の局所比較で、Kaggle official score `0.25`の内訳やhidden性能を示さない。

## 採否と次工程

candidate v4は追加seedでもrandom baselineを上回るlevels/no-op傾向を示したが、完了levelはrun seedで変動しWINはなかった。環境seedとpolicy RNGが交絡しているため、runtime乱数の制御変更はまだ採用しない。次工程は評価器に環境seedとpolicy seedを分離する診断オプションを追加し、同じ公開開始条件のままpolicy RNGだけを変えたC6-003とする。

## 再現・証拠

- 7つのseed別artifactは`出力/ARC3-RUN-002-local/C6-002-seed-<seed>.json`。個別game ID・盤面・Action列を含むため、集計報告には転記していない。
- 匿名summary: `出力/ARC3-RUN-002-local/C6-002-seed-stability-summary.json`、SHA-256 `C35BE3472D4EC57B13A36084AC7EAA901AD223ED1FF90E840FE8AC0F3E7C6FCB`。
- evaluation runner SHA-256 `9F936FE5E12BD545E33DF7BF1C0911EFDBBA04EA362AB6FD05027D3E783294D8`。candidate workspace policy SHA-256 `325666AE54197474E33B4FF46306ABC7AD12C7A489D2C2C3C59585D887E26510`。
- 追加artifact SHA-256: seed11 `7B08BC21A4097E0F57A524D129BEA005710CA44D606D01C972D819BD55A0FDC9`; seed17 `E4053F40153D5D686F9C23DEE6EF0069B43ACE187D89D325DDB8CBE5819B92D8`; seed29 `9DCD6BDAAD04C2FE8C8206B765B6FFB345066D013BA66322235A0EE591D8A069`; seed43 `1BC1BB241102A8375D986E909FCD5E670139719E1B12C165623915A0BBF7F60F`; seed59 `04E09DC748A9977A15A7CE4AF702D79D0EC05BECF83A1B53677DFF44BCBB399B`; seed83 `603A0842FE47DD07C2C07F651777192F6E8847C593DA1D102DBDFEEA39269300`; seed101 `2A22BA32FEF61731C64C83F3B340DC420E8AB14DB16171800501183EFB68DF65`.
