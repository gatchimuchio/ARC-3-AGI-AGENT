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
