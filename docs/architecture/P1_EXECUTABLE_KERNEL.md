# P1 Executable Kernel 実装境界

- phase: `P1_EXECUTABLE_KERNEL`
- state: implementation closed / completion gate `SUSPEND`
- runtime scope: independent / offline / deterministic
- official runner: not connected
- benchmark claim: none

## Work contract

```text
X:
  current rendered observation
  identity-free raw input
  independent arc3_agi_agent package

R:
  symbolization -> bounded context
  HDS command -> Pure-LLM hypotheses/candidates
  fitting -> W=(X,R,Mc)
  HDS judgment -> authorized write/emit
  emission result -> HDS observation

Mc:
  six callable responsibilities
  unique single-role removal witnesses
  HDS-only command/judgment/authorization
  capability-backed HDS decision/directive provenance
  passive memory
  unavailable or unclosed action rejection
  STOP terminality
  deterministic candidates/closure/digest/trace
```

非目的:

- 公式runnerのaction-selection変更
- live ARC environmentへのaction送信
- task/game/level別攻略
- replay、固定action列、answer map、literal座標
- score評価・閾値最適化
- AGI完成、汎化達成、満点対応の主張

## Callable responsibilities

| Responsibility | Callable boundary | State owner / output |
|---|---|---|
| `SYMBOL_SPACE` | `DeterministicSymbolSpace.encode` | `ObservationIR` |
| `CONTEXT_STATE` | `BoundedContextState.ingest/condition/record_emission` | `ContextSnapshot` |
| `TRANSFORM_OR_WORLD_MODEL` | `DeterministicWorldModel.transform` | competing `HypothesisIR` |
| `CANDIDATE_SURFACE` | `DeterministicCandidateSurface.generate` | action/probe/reobserve/SUSPEND/STOP/rollback/plan |
| `FITTING_OR_SUCCESS_CRITERION` | `DeterministicSuccessCriterion.evaluate` | `ClosureIR` with `X/R/Mc` |
| `EMISSION_INTERFACE` | `InMemoryEmissionInterface.emit` | authorized `EmissionResult` |

Fittingは次の軸を各action候補へ記録します。

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
  -> Pure-LLM computes hypotheses and candidates
  -> fitting constructs closure proposals
  -> HDS accepts, rejects, suspends, or stops
  -> Pure-LLM executes only HDS directives
  -> passive memory and emission boundary apply authorized operations
  -> HDS observes the result
```

HDS does not mutate memory or invoke the environment adapter directly.
Memory exposes no autonomous compute/update path.
The in-memory adapter does not send a live ARC action.

## Required trace

```text
SELF_CHECK
FRAME / SYMBOL_SPACE
CONTEXT_STATE update
passive memory read
HDS compute command
Pure-LLM hypothesis/candidate proposal
FITTING closure proposal
HDS decision
authorized in-memory emission
HDS result observation
authorized passive-memory write
REFRAME or SUSPEND or STOP
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

`run_required_removal_audit` replaces the actual callable dependency with
`None`. It does not remove a role label from metadata. A missing callable or
invalid output is separately rejected as a nonfunctional implementation.

## Closed in P1

- one independent HDS-controlled cycle
- multiple competing hypotheses and candidate modes
- conservative `SUSPEND`, hazard veto, and STOP terminality
- candidate ID, closure signature, action availability, and HDS permission gates
- HDS-authorized passive-memory mutation
- authority labelsだけでは通らないHDS capability検証
- HDS側でclosure field、fit score、hazard、terminal、budget、actionを再検証
- identity-key rejection across snake_case, camelCase, and PascalCase
- deterministic candidate order, closure, digest, and trace
- full-set and six single-role removal audit

## Not closed in P1

- official runner integration
- live environment transport and post-action rendered verification
- environment rollback guarantee
- multi-cycle stale-frame/version-conflict handling
- persistent memory backend
- benchmark re-establishment or score improvement
- hidden-task generalization evidence
- repository-wide unit gate repair for the pre-existing `agents.structs` and
  eager optional-dependency collection failures

## Validation

P1独立kernel:

```bash
python -m compileall -q ARC-AGI-3-Agents/arc3_agi_agent

python -m unittest discover \
  -s ARC-AGI-3-Agents/tests/unit \
  -p "test_arc3_agi_*.py" \
  -v

python -m pytest -q --confcutdir=ARC-AGI-3-Agents/tests/unit \
  ARC-AGI-3-Agents/tests/unit/test_arc3_agi_foundation.py \
  ARC-AGI-3-Agents/tests/unit/test_arc3_agi_kernel.py

git diff --check
```

Repository-wide completion gate:

```bash
python -m unittest discover \
  -s ARC-AGI-3-Agents/tests/unit \
  -p "test_*.py" \
  -v

python -m pytest -q ARC-AGI-3-Agents/tests/unit
```

後者は現在のHEADで、P1外の`tests/unit/test_core.py`、
`tests/unit/test_swarm.py`、`tests/conftest.py`が参照する
`agents.structs`の欠落と、`agents/__init__.py`によるoptional dependencyの
eager importで収集停止します。この既存障害をP1実装へ混入して修復せず、
完了判定を`SUSPEND`に保持します。
