# P1 Executable Kernel 実装境界

- phase: `P1_EXECUTABLE_KERNEL`
- state: complete / HDS judgment `PASS`
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
- current `arcengine` / `Arcade` APIに整合したrepository-wide unit harness
- optional agent dependencyを選択時まで読み込まないlazy import boundary
- `agents`と`arc3_agi_agent`を明示的に含むinstallable package

## Not closed in P1

- official runner integration
- live environment transport and post-action rendered verification
- environment rollback guarantee
- multi-cycle stale-frame/version-conflict handling
- persistent memory backend
- benchmark re-establishment or score improvement
- hidden-task generalization evidence

## Validation

P1 completion gate:

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

ruff check \
  ARC-AGI-3-Agents/arc3_agi_agent \
  ARC-AGI-3-Agents/agents/__init__.py \
  ARC-AGI-3-Agents/agents/recorder.py \
  ARC-AGI-3-Agents/tests/conftest.py \
  ARC-AGI-3-Agents/tests/unit

git diff --check
```

2026-07-23の完了監査では、`unittest` 30件、`pytest` 84件、
compile、ruff、`uv sync --locked`、editable install、isolated wheel buildが
すべて通過しました。
full setと六つのsingle-role removal、権限拒否、task identity-free、
決定性の各証拠はunit suite内で実行されています。公式runnerの
action-selection実装は変更していません。
