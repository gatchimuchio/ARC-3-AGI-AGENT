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

上記四fileはv14以前のbaseline証拠として保持する。現行active Pは
`p10-hybrid-v21`であり、HDS採用済みの再現可能なlevel境界は
30 / 183へ更新された。

## P update v14 promotion evidence

`p_update/iteration_14_regression/`をv14の正本証拠directoryとする。

| file | role |
|---|---|
| `p10_candidate_compile_trace_v1.json` | HDS-approved MからのP-B学習、同一入力C差分、stable/target二回回帰 |
| `p10_promotion_receipt_v1.json` | HDS PROMOTE判断、single-use directive、previous/active digest |
| `p_b_learning_dataset_v1.json` | HDS承認済みMから構成した決定論的dataset |
| `p_b_learning_memory_v1.json` | 学習入力となった受動M snapshot |
| `p_b_learning_result_v1.json` | parameter差分、holdout比較、attribution |
| `p10_active_post_promotion_su15.json` | ACTIVE昇格後の9 / 9、175 actions、reset 0 |

候補はstable 20 / 20を維持し、targetをprevious stableの7 / 9から9 / 9へ
改善した。同条件二回のselected-field digestは一致し、HDSの全十promotion
gateがPASSした。中間iterationのraw reportとsuperseded bundleは正本へ
含めず、`M_dev`の無制限追記を避ける。

全25 gameのcanonical 450-action逐次runは外部commandの7200秒timeoutに達し、
完了reportを生成できなかった。この失敗はP10 agentのmax-action停止と分離し、
full scoreおよび183 / 183の証拠には使用しない。P10全体は`HOLD`である。

## P update v16 promotion evidence

`p_update/iteration_16_regression/`をv16の正本証拠directoryとする。

| file | role |
|---|---|
| `p10_candidate_compile_trace_v1.json` | 旧29 level回帰、target 0→1、同条件再実行、P-B同一入力差分 |
| `p10_promotion_receipt_v1.json` | HDS PROMOTE判断、single-use directive、previous/active digest |
| `p_b_learning_dataset_v1.json` | HDS承認済みMから構成した決定論的dataset |
| `p_b_learning_memory_v1.json` | 学習入力となった受動M snapshot |
| `p_b_learning_result_v1.json` | parameter差分、holdout比較、attribution |
| `p10_active_post_promotion_ka59.json` | ACTIVE昇格後の1 / 7、64 actions、error 0 |

候補は既存29 levelを同じactionsで維持し、bounded targetをprevious stableの
0 / 7から1 / 7へ改善した。同条件二回のtarget run digestは一致し、HDSの
全十promotion gateがPASSした。active manifest digestは
`4e19e461a7f0d65573782be5e2bddc873ba62d5bfe76ef2f1e42293ac2dd32cc`。
ただしtargetは`MAX_ACTION_STOP`で残り6 levelが未完了であり、完全な
25 game / 183 level reportも存在しない。したがって30 / 183は採用済み
level境界であって、ローカルオラクルのfull scoreではない。
