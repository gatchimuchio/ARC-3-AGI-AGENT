# P10 execution evidence

このdirectoryは、保持済みOFFLINE sampleをP10 runtimeで実行した結果を
保存する。sample/game識別子は結果を同定する監査metadataに限り許可し、
P bundle、C selector、M payload、runtime routingには使用しない。

## `ft09_variant_comparison.json`

- schema: `arc3-p10-execution-evidence-v1`
- condition: OFFLINE、action budget 256、同一sample、seed 0
- variants: P-A / P-B / hybrid
- P-A: 6 / 6、75 actions、WIN
- P-B: 0 / 6、256 actions、MAX_ACTION_STOP
- hybrid: 6 / 6、75 actions、WIN
- error: 全variant 0
- content digest:
  `8d17b068a757ececded6c4f2a7669a57319a12e3194e5c8ca1d9c956f213f473`

各stable runはagent reportの全`trace_events`、trace digest、P format/version/
digest、M operation/version、HDS decision/verification、rollback/search-reset
証拠を保持する。local scorecard IDのような非決定的metadataだけを除外した。

この証拠はPの有無による能力差とFT09の6 level完了だけを示す。
全25 game / 183 level完了、未知構造への一般汎化、P11 release stateを
証明しない。

## 現行hybrid compact evidence

compact evidenceは、全cycleのtrace digest、trace event root、実emit、
provenance、level transition、P digest、M version、rollback/reset欄を保持する。
local scorecard identityと重複するtrace event本体は除外し、event本体全体を
`trace_events_digest`へ束縛する。

| file | 完了 | actions | 終端 | content digest |
|---|---:|---:|---|---|
| `ft09_hybrid_active_compact.json` | 6 / 6 | 75 | `WIN` | `6680518299ed6952bcd99cb300f8118e02a96045f22acea4acde7339f8e54ab0` |
| `lp85_hybrid_compact.json` | 8 / 8 | 235 | `WIN` | `834907e467bc0ae1fb0130a3c9a06da2cefeb7ae8a700cbc9e090ce8cbb248d4` |
| `tr87_hybrid_compact.json` | 6 / 6 | 308 | `WIN` | `fd2ea2dd39f378228446b4cb3847c8f97741e5b9105203081e693784dda5f9e4` |
| `su15_hybrid_active_failure_compact.json` | 4 / 9 | 160 | `MAX_ACTION_STOP` | `10442999cd46639c281cc717bb937166dc3c1a9d5ab1c167b0a8307b03b2bec2` |

現行active Pは`p10-hybrid-v5`、visual operatorは
`arc3-p10-visual-operator-v12`である。最初の三実行はaction budget 512で
20 / 20 levelを再完了した。SU15では追加4 levelのtransitionを観測したが、
budget 160でlevel 5が停止したためstable full-game採用境界は20 / 183、
P10は`HOLD`のままである。
