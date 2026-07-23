# P1 Sample Execution Mechanism 実装境界

- phase: `P1_SAMPLE_EXECUTION_MECHANISM`
- state: complete / HDS judgment `PASS`
- runtime scope: bundled official samples / offline / bounded
- sample runner: `ARC-AGI-3-Agents/sample_main.py`
- online / competition runner: not connected or changed
- benchmark claim: none
- Pure-LLM compute subject claim: **not closed because instruction body P is not yet independent**

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

命令形保持体Pの形成・接続は `P2_INSTRUCTION_BODY_FORMATION.md` の対象である。

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
HDS issues a single-use compute capability
  -> Layer-0 mechanism executes provisional embedded rules
  -> fitting constructs closure proposals
  -> HDS accepts, rejects, suspends, or stops
  -> execution surface performs only HDS directives
  -> passive memory and emission boundary apply authorized operations
  -> HDS observes the result
```

HDS does not mutate memory or invoke the environment adapter directly。
Memory exposes no autonomous compute/update path。
Execution calls the OFFLINE adapter only with a capability-backed HDS directive。The sample agent's direct action methods always reject。

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
- capability-backed HDS authorization
- HDS-side closure revalidation
- identity-key rejection across common naming forms
- deterministic candidate order、closure、digest、trace
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
