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

| file | 完了 | actions | content digest |
|---|---:|---:|---|
| `ft09_hybrid_active_compact.json` | 6 / 6 | 75 | `db66f118946fab5b7bb4e323fc10f25d91597209b6e1bf847367072fcd0cfdae` |
| `lp85_hybrid_compact.json` | 8 / 8 | 235 | `c330030a57d8005faea8b1f95dc4631f25bdaef21207a2f19751b9d41e3ccdcc` |
| `tr87_hybrid_compact.json` | 6 / 6 | 308 | `d0468d345b502468a12932784e116fa73bc087718b2ff471d873064ce44196dc` |

三実行のactive Pは`p10-hybrid-v3`、visual operatorは
`arc3-p10-visual-operator-v7`である。合計は20 / 183であり、P10は
`HOLD`のままである。
