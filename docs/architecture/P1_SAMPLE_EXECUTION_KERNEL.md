# P1 Sample Execution Mechanism 実装境界

- phase: `P1_SAMPLE_EXECUTION_MECHANISM`
- state: complete / HDS judgment `PASS`
- runtime scope: bundled official samples / offline / bounded
- sample runner: `ARC-AGI-3-Agents/sample_main.py`
- online / competition runner: not connected or changed
- benchmark claim: none
- Pure-LLM compute subject claim at P1: **not closed**
- superseded status: P4で独立Pとstandalone Cを実装済み

## 0. 再分類

P1で完成したのは次である。

```text
Layer-0 execution mechanism
+ HDS / Memory authority loop
+ OFFLINE sample action / re-observation path
```

P1では、現行 `roles.py` の固定規則を使用して仮説・候補を生成している。Layer-0が参照・選択・合成して実行する独立命令形保持体 `P` はまだ存在しない。

したがって、P1は次を証明していない。

```text
C = Execute(L0, P)
```

命令形保持体Pの形成・接続は
`P4_COMPUTE_SUBJECT_IMPLEMENTATION.md`の対象である。

## Work contract

```text
X:
  bundled 25 official sample games / 183 levels
  current rendered FrameDataRaw
  identity-free raw input
  arc3_agi_agent + OFFLINE sample agent / runner

R:
  symbolization -> bounded context
  HDS command -> provisional embedded-rule computation
  fitting -> W=(X,R,Mc)
  HDS judgment -> authorized OFFLINE step
  rendered result -> HDS observation / verifier
  context + passive memory -> next HDS cycle

Mc:
  six callable responsibilities
  unique single-role removal witnesses
  HDS-only command/judgment/authorization
  capability-backed HDS decision/directive provenance
  observation / context / memory-bound compute command
  one decision per command
  single-use write / emit directives
  candidate, frame, payload, and result provenance binding
  passive memory
  unavailable or unclosed action rejection
  STOP terminality
  OperationMode.OFFLINE fixed
  no direct Agent action path
  max-action bound
  deterministic candidates/closure/digest/trace
```

非目的:

- 命令形保持体Pの完成
- Pure-LLM計算主体全体の完成
- 保持済みsampleの全level攻略
- 既存HTTP / online runnerのaction-selection変更
- 公式ARC API / `OperationMode.COMPETITION`
- Kaggle code、Notebook、CLI / MCP提出
- task/game/level別攻略
- replay、固定action列、answer map、literal座標
- score評価・閾値最適化
- AGI完成、汎化達成、満点対応の主張

## Callable responsibilities

| Responsibility | Callable boundary | State owner / output |
|---|---|---|
| `SYMBOL_SPACE` | `DeterministicSymbolSpace.encode` | `ObservationIR` |
| `CONTEXT_STATE` | `BoundedContextState.ingest/condition/record_emission` | `ContextSnapshot` |
| `TRANSFORM_OR_WORLD_MODEL` | `DeterministicWorldModel.transform` | provisional competing `HypothesisIR` |
| `CANDIDATE_SURFACE` | `DeterministicCandidateSurface.generate` | provisional action/probe/control candidates |
| `FITTING_OR_SUCCESS_CRITERION` | `DeterministicSuccessCriterion.evaluate` | `ClosureIR` with `X/R/Mc` |
| `EMISSION_INTERFACE` | `InMemoryEmissionInterface.emit` / `OfflineArcadeEmissionInterface.emit` | authorized result / rendered sample result |

`TRANSFORM_OR_WORLD_MODEL`と`CANDIDATE_SURFACE`はP1では機構と固定seed情報が混在している。P2でmechanismとinstruction bodyを分離する。

Fittingは次の軸を各action候補へ記録する。

```text
progress
goal relevance
hazard
terminal state
expected effect consistency
information gain
uncertainty
repetition cost
rollback cost
action budget
```

## Asymmetric Trinity

```text
HDS issues a single-use compute capability bound to observation / context / memory
  -> Layer-0 mechanism executes provisional embedded rules
  -> fitting constructs closure proposals
  -> HDS accepts, rejects, suspends, or stops exactly once
  -> HDS binds a single-use emit directive to candidate / closure / frame
  -> execution surface performs only that HDS directive
  -> emission boundary binds its one-shot receipt to result content and provenance
  -> HDS observes and validates the result
  -> HDS binds a single-use memory directive to the judged payload
  -> passive memory applies the authorized operation once
  -> HDS verifies context / memory updates and alone finalizes PASS
```

HDS does not mutate memory or invoke the environment adapter directly.
Memory exposes no autonomous compute/update path.
The execution surface calls the OFFLINE adapter only with a capability-backed
HDS directive. Copying or reusing a directive, replacing the judged candidate
or frame, changing the approved memory payload, tampering with the observed
result, or returning a result without its content-bound execution receipt is
rejected. The sample agent's direct action methods always reject.

## Required trace

```text
Arcade(OperationMode.OFFLINE)
rendered FrameDataRaw
FRAME / SYMBOL_SPACE
CONTEXT_STATE update
passive memory read
HDS compute command
provisional hypothesis/candidate proposal
FITTING closure proposal
HDS decision / closure revalidation
authorized OFFLINE environment step
rendered result observation / transition verification
authorized passive-memory write
next FRAME with previous/current context
REFRAME, SUSPEND, REJECT, or STOP
```

## Fixed removal witnesses

| Removed callable | Fixed failure witness |
|---|---|
| `SYMBOL_SPACE` | `SYMBOL_SPACE_REMOVED_INPUT_NOT_SYMBOLIZED` |
| `CONTEXT_STATE` | `CONTEXT_STATE_REMOVED_HISTORY_NOT_CONDITIONED` |
| `TRANSFORM_OR_WORLD_MODEL` | `TRANSFORM_OR_WORLD_MODEL_REMOVED_NO_HYPOTHESIS_OR_PREDICTION` |
| `CANDIDATE_SURFACE` | `CANDIDATE_SURFACE_REMOVED_NO_COMPARABLE_CANDIDATES` |
| `FITTING_OR_SUCCESS_CRITERION` | `FITTING_OR_SUCCESS_CRITERION_REMOVED_NO_CLOSURE_BASIS` |
| `EMISSION_INTERFACE` | `EMISSION_INTERFACE_REMOVED_NO_AUTHORIZED_BOUNDARY` |

`run_required_removal_audit` replaces the actual callable dependency with `None`。It does not remove a role label from metadata。A missing callable or invalid output is separately rejected as a nonfunctional implementation。

P removal witnessはP2で追加する。

```text
INSTRUCTION_BODY_REMOVED_NO_EXECUTABLE_KNOWLEDGE_OR_TRANSFORM
```

## Closed in P1

- one independent HDS-controlled execution cycle
- multiple provisional hypotheses and candidate modes
- conservative `SUSPEND`, hazard veto, and STOP terminality
- candidate ID、closure signature、action availability、HDS permission gates
- HDS-authorized passive-memory mutation
- authority labelsだけでは通らないHDS capability検証
- compute commandを発行時のobservation / context / memoryへ束縛
- judgment inputを発行時observationと正規conditioned contextへ束縛
- controllerが発行したcompute command実体だけを受理
- 一つのcompute commandから一つのdecisionだけを発行
- emit / memory directiveを発行実体へ所有者束縛し、copy / replayを拒否
- memory writeをjudged payload digestとemission再観測へ束縛
- emitをjudged candidate content、closure、frameへ束縛
- result contentへ束縛したreceipt、command、decision、candidate、closure、frameを照合した結果再観測
- emission、context、memoryの実結果を再照合したHDS-only cycle finalization
- HDS側でclosure field、fit score、hazard、terminal、budget、actionを再検証
- hazard / `GAME_OVER` vetoをunknown state・budget停止より優先
- identity-key rejection across snake_case, camelCase, and PascalCase
- deterministic candidate order, closure, digest, and trace
- full-set and six single-role removal audit
- bundled sample observation to identity-free IR
- `OperationMode.OFFLINE` fixed
- `LocalEnvironmentWrapper` requirement
- HDS-authorized local sample `step`
- dynamic ACTION6 coordinates from current frame dimensions
- actual rendered effects into context
- action-result re-observation and next HDS judgment
- bundled 25-game one-action / no-network smoke
- optional recording and JSON report
- repository-wide unit harness
- installable sample agent / runtime / adapter / CLI

## Not closed in P1

- independent executable instruction body `P`
- P-A symbolic / rule graph body
- P-B parametric / neural body
- same-Layer-0 instruction-body swap
- sample-derived rule compile / parameter training
- P / M version and update-boundary separation
- P removal audit
- full sample game / all 183 level solving
- GAME_OVER、timeout、infinite-loop、max-action resolution
- complete-sample reproducibility / regression freeze
- official API / competition connection
- Kaggle Notebook / CLI / MCP / submission
- environment rollback guarantee
- persistent memory backend
- benchmark re-establishment or score improvement
- hidden-task generalization evidence

## Validation

P1 regression gate:

```bash
python -m compileall -q \
  ARC-AGI-3-Agents/arc3_agi_agent \
  ARC-AGI-3-Agents/agents \
  ARC-AGI-3-Agents/tests/unit

python -m unittest discover \
  -s ARC-AGI-3-Agents/tests/unit \
  -p "test_*.py" \
  -v

python -m pytest -q ARC-AGI-3-Agents/tests/unit

python -m mypy ARC-AGI-3-Agents/arc3_agi_agent

python -m unittest discover \
  -s ARC-AGI-3-Agents/tests/integration \
  -p "test_offline_sample_runner.py" \
  -v

python ARC-AGI-3-Agents/sample_main.py \
  --all-samples \
  --max-actions 1

ruff check \
  ARC-AGI-3-Agents/arc3_agi_agent \
  ARC-AGI-3-Agents/agents/__init__.py \
  ARC-AGI-3-Agents/agents/recorder.py \
  ARC-AGI-3-Agents/tests/conftest.py \
  ARC-AGI-3-Agents/tests/unit

git diff --check
```

2026-07-23のsample接続監査では、保持済み25ゲームを各1 actionだけ実行し、25/25でHDS承認、OFFLINE step、再観測、context / memory更新、次HDS判断が成立した。全25件のrendered transition判定は、level progress未観測のため正規出力`SUSPEND`で、`FAIL`は0件であった。

この結果はP1実行経路の証拠であり、Pure-LLM計算主体、P形成、sample攻略の証拠ではない。

## 2026-07-23 権限境界の再監査

初回実装を攻撃的に再実行し、次の不適合をbase commit上で再現して是正した。

| Pre-fix witness | Correction | Post-fix result |
|---|---|---|
| command発行後にobservationを差し替えてcomputeできた | observation / context / memory snapshotをcommandへ束縛 | `HDS_COMMAND_*_MISMATCH`で拒否 |
| Pythonの`True`がaction 1へ正規化された | `bool`をinput / candidate / directiveの全境界で非action化 | boolean actionを候補採用・放出しない |
| kernel自身がcycle statusを`PASS`へ設定していた | HDSがemission / context / memory実結果を再照合してfinalize | HDS以外に最終`PASS`設定経路なし |
| 同じemit directiveで2 actionを実行できた | directiveをone-shot grantへ変更 | 2回目を`EXTERNAL_EMIT_DIRECTIVE_ALREADY_CONSUMED`で拒否 |
| 同じmemory directiveでversionが1から2へ進んだ | payload digest束縛とone-shot consume | 2回目を拒否しversion 1を維持 |
| receiptのない偽`EmissionResult`をHDSが受理した | resultへ完全なprovenanceとexecution receiptを要求 | `EMISSION_RESULT_AUTHORIZATION_RECEIPT_INVALID`で拒否 |
| 正規resultのreceiptを改変コピーへ流用できた | receiptを全result contentのdigestへ一回だけ束縛 | visible effect / terminal改変をreceipt不一致で拒否 |
| directiveコピーが元grantを先に消費できた | grantをHDS発行directive objectへ所有者束縛 | emit / memoryともcopyを環境操作・write前に拒否 |
| 同じcompute commandから複数decisionを発行できた | command所有権とjudged stateをHDS内で保持 | `HDS_COMMAND_ALREADY_JUDGED`で拒否 |
| budget枯渇が`GAME_OVER` / hazardを覆い隠した | hazard vetoをunknown / budget判定より優先 | `HAZARD_ACTION_VETO`を保持 |
| emission後のhazardを最終`PASS`としてmemoryへ書けた | HDSがemission resultを再判断し、hazard時はwriteせず`REJECT` | memory version 0とfailure evidenceを維持 |
| P1 packageに型エラーが5件残っていた | callable cast、tuple型、removal mutationを明示 | `mypy arc3_agi_agent`合格 |

同一最終差分に対する再監査gate:

- Python: `3.12.13`
- compile: 合格
- unit `unittest`: 52件合格
- unit `pytest`: 106件合格
- repository `pytest`: 108件合格
- `mypy arc3_agi_agent`: 16 source files合格
- `ruff`: 合格
- OFFLINE integration: 2件合格
- full set: `PASS`
- six single-role removals: 固定した六つの固有failure witnessで全件`FAIL`
- same-input determinism: candidate / closure / trace / digest一致
- OFFLINE sample smoke: 25/25完了、error 0、各1 action、memory version 1
- transition verification: 25/25が保守的`SUSPEND`、`FAIL` 0
- network guard: request / socketを強制失敗させた状態でintegration合格
- wheel: sample agent / runtime / adapter / CLIと`arc3-p1-samples` entry pointを確認
- wheel SHA-256: `bd8fa3edec8ad981d9ab09a673799edf00aba847ffd5542575b9adb51f6ec8c1`

このgateはP1 execution mechanismの回帰証拠である。独立した命令形保持体`P`、
P-A / P-B、`C = Execute(L0, P)`、sample攻略、汎化性能の証拠ではない。
