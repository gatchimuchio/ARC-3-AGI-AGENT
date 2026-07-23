# P10 ARC3全sample攻略・実装監査

- phase: `P10_COMPLETE_ARC3_SAMPLE_SOLVING`
- state: `IN_PROGRESS`
- predecessor: `P9_EIGHT_SUBSET_MINIMUM_CERTIFICATE`
- successor: `P11_RELEASE_STATE_FREEZE`
- operation mode: `OFFLINE` only
- HDS judgment: `HOLD`

## 1. Work-block FrameSpec

```text
X:
  保持済み25 sample / 183 levelのrendered observation、available action、
  bounded context、identity-free P、受動M、HDS Frame、OFFLINE adapter

R:
  HDS command
  -> Cがrendered sceneとHDS承認済みMを計算
  -> Jが候補を採否
  -> capability-bound external emit
  -> result再観測
  -> J再判断
  -> 許可済みM更新またはrollback
  -> 次cycleの計算・判断変更

Mc:
  183/183、error 0、GAME_OVER 0、timeout 0、無限loop 0、
  max-action停止0、同一条件再実行一致、runtime identity leak 0、
  M因果あり、明示的P version更新、全trace保存でPASS

non-goals:
  公式API、COMPETITION、Kaggle、submission、P11凍結

evidence boundary:
  sourceは解析・反証専用
  runtimeはrendered observation、available action、action/effect history、
  identity-free P/Mだけを使用

falsification:
  ID/replay/fixed action/answer/literal coordinate/source/hidden-state routing、
  capabilityなしRESET、失敗握り潰し、未完了を全攻略と表記

regression:
  P0〜P9 unit / integration / certificate、strict mypy、ruff、compileall
```

## 2. 現在の実装ブロック

`arc3_agi_agent/visual_explorer.py`は、rendered gridから同色連結成分、
status候補、単純action、観測由来click候補を形成し、遷移・無変化・hazardを
versioned payloadへ直列化する。game/task/level IDを入力に取らない。

`arc3_agi_agent/p10_compute.py`はP1 kernelを変更せず、HDS commandの配下で
最新の承認済みMを読み、P10候補とM更新案を生成する。cycle 1のMにより
cycle 2の候補actionが変わることを単体試験で固定している。

`arc3_agi_agent/p10_instruction_compiler.py`は、P4 predecessorからP-A、
P-B、hybridをseed 0で決定論的にcompileする。意味演算子のdetector、
transform、parameter、precondition、falsifierはP-A/hybridだけに入り、
P-Bからは除去される。P交換時はinstruction digestを照合し、旧P由来queue、
transition model、constraint stateを無効化する。

`arc3_agi_agent/semantic_operators.py`は、rendered relation tile latticeを
GF(2)または循環差分で解く演算子と、rendered target/controlの作用対応を
一手再観測、transition graph、coordinate descent、permutation modelで
学習する演算子を持つ。

`arc3_agi_agent/symbolic_rewrite.py`はbordered symbol、connector、source/
output row、selectorをrenderから検出する。fixed rewriteを直接適用し、
editable ruleは各visible nodeのcycleを観測した後、有界constraintとして
解く。三演算子ともgame/task/level ID、source、hidden state、固定座標を
受け取らず、内部stateはversioned passive M payloadへ直列化される。

`arc3_agi_agent/recovery.py`とOFFLINE adapterは、観測済みGAME_OVERに対して
HDSがrollback Frameを判断し、single-use capabilityを発行した場合だけ、
Pure-LLM executorによるM rollback、failure保持、RESET、再観測を許す。
偽造directiveと二重RESETは拒否する。

`arc3_agi_agent/search_reset.py`はGAME_OVER recoveryと分離されている。
現在branchから未試行frontierへ到達できず、初期rendered state側にだけ
frontierが残ることをCが証拠化し、HDSがFrameを閉じた場合だけ、Mを保持して
環境RESETを1回実行する。RESETごとに新しいsingle-use capabilityを要求する。

`agents/templates/p10_sample_agent.py`と`p10_main.py`は、通常actionとRESETの
双方を上記権限境界だけから実行し、full trace、P digest、M version、
rollback decision、完了数をreportする。

作業Mは同一targetへ毎cycle追加しない。初回はHDSが`ADD`、後続は観測時の
active targetを確認して`REPLACE`を許可する。version/historyは維持しつつ、
current snapshotの重複増大を防ぎ、各cycleのtraceはreport側へ残す。

## 3. 現在の実測境界

P10実行経路の関連unit、strict mypy、ruff gateは通過している。現行hybrid
`p10-hybrid-v3`、visual operator `arc3-p10-visual-operator-v7`、
OFFLINE、seed 0の実測は次のとおりである。

| rendered mechanism | 完了 | actions | M影響cycle | recovery | reset | 終端 |
|---|---:|---:|---:|---:|---:|---|
| relation-toggle | 6 / 6 | 75 | 69 | 0 | 0 | `WIN` |
| object-target control | 8 / 8 | 235 | 188 | 0 | 0 | `WIN` |
| symbolic rewrite | 6 / 6 | 308 | 284 | 0 | 0 | `WIN` |

全実行でerror 0、GAME_OVER 0、max-action停止なしを確認した。現時点で
新runtimeが実証した完了数は`20 / 183`で、未実証は`163 level`である。
これは三つの意味演算子blockの採用証拠であり、全sample攻略証拠ではない。

FT09、action budget 256、seed 0、OFFLINEの同一条件比較:

| P variant | P version | 完了 | actions | 終端 |
|---|---|---:|---:|---|
| P-A | `p10-p-a-symbolic-v2` | 6 / 6 | 75 | `WIN` |
| P-B | `p10-p-b-parametric-v2` | 0 / 6 | 256 | `MAX_ACTION_STOP` |
| hybrid | `p10-hybrid-v1` | 6 / 6 | 75 | `WIN` |

全variantでruntime errorは0だった。P-Bではsemantic operator instructionが
0件であり、CコードとM内queueを同じままにしても能力が消失した。これは
当該能力がPの明示内容へ依存することのP10実行証拠である。

初期relation-toggleの全cycle traceを含むscorecard非依存の安定射影は
[`ft09_variant_comparison.json`](../../evidence/p10/ft09_variant_comparison.json)
へ保存した。content digestは
`8d17b068a757ececded6c4f2a7669a57319a12e3194e5c8ca1d9c956f213f473`
である。game IDは実行結果を同定するevidence fieldにだけ存在し、P、C、
M、runtime selectorへは入らない。

現行Pの三実行は、各cycleのtrace digest、trace-event root、実emit、
provenance、level transition、P digest、M version、rollback/reset欄を保持する
compact evidenceへ固定した。

- [`ft09_hybrid_active_compact.json`](../../evidence/p10/ft09_hybrid_active_compact.json):
  `db66f118946fab5b7bb4e323fc10f25d91597209b6e1bf847367072fcd0cfdae`
- [`lp85_hybrid_compact.json`](../../evidence/p10/lp85_hybrid_compact.json):
  `c330030a57d8005faea8b1f95dc4631f25bdaef21207a2f19751b9d41e3ccdcc`
- [`tr87_hybrid_compact.json`](../../evidence/p10/tr87_hybrid_compact.json):
  `d0468d345b502468a12932784e116fa73bc087718b2ff471d873064ce44196dc`

compact evidenceは省略したtrace event本体を`trace_events_digest`へ束縛する。
raw reportはlocal実行証拠であり、非決定的scorecard identityをrelease
artifactへ持ち込まない。

一方、rendered transition graphだけによる探索は全sample攻略を閉じない。
G50T level 1の診断では188 action、1 reset、25 visible nodeでfrontierが
尽き、進捗は0だった。status候補をstate signatureから除外しない診断は
状態空間が急増し、300秒以内に進捗を得なかった。

これはP10完了証拠ではなく、履歴位相・役割・目標・commit条件を持つ
identity-free演算子が残りの構造にも必要であるという反証である。したがって
現時点のHDS判断は`HOLD`とし、P11へ進めない。

## 4. 実行入口

```bash
cd ARC-AGI-3-Agents
python -m arc3_agi_agent.p10_instruction_compiler \
  --base-bundle-dir arc3_agi_agent/bundles \
  --output-dir arc3_agi_agent/bundles
python p10_main.py --game FT09 --instruction-variant hybrid \
  --max-actions 4096
python p10_main.py --all-samples --max-actions 4096 \
  --instruction-variant hybrid \
  --report ../evidence/p10/run.json
```

`p10_main.py`は全選択gameが`WIN`でない限り終了code 1を返す。

## 5. 次の採否gate

追加する演算子は、現在frameと許可されたhistoryから適用条件を再導出し、
同一構造へ再利用できなければならない。旧資産のID router、level counter
router、replay、固定列、literal座標は移植しない。

各演算子は次を満たした場合だけactive Pへcompileする。

1. identity-free detectorとplannerを別々に試験する
2. 現行Pとの同一条件比較で完了levelを減らさない
3. failureがMへ保持され次判断を変える
4. source/hidden-state runtime参照が0
5. 全traceでHDSが最終採否主体である
