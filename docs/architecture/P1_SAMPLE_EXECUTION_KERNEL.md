# P1 Sample Execution Kernel 実装境界

- phase: `P1_SAMPLE_EXECUTION_KERNEL`
- state: complete / HDS judgment `PASS`
- runtime scope: bundled official samples / offline / bounded
- sample runner: `ARC-AGI-3-Agents/sample_main.py`
- online / competition runner: not connected or changed
- benchmark claim: none

## Work contract

```text
X:
  bundled 25 official sample games / 183 levels
  current rendered FrameDataRaw
  identity-free raw input
  arc3_agi_agent + OFFLINE sample agent / runner

R:
  symbolization -> bounded context
  HDS command -> Pure-LLM hypotheses/candidates
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
| `TRANSFORM_OR_WORLD_MODEL` | `DeterministicWorldModel.transform` | competing `HypothesisIR` |
| `CANDIDATE_SURFACE` | `DeterministicCandidateSurface.generate` | action/probe/reobserve/SUSPEND/STOP/rollback/plan |
| `FITTING_OR_SUCCESS_CRITERION` | `DeterministicSuccessCriterion.evaluate` | `ClosureIR` with `X/R/Mc` |
| `EMISSION_INTERFACE` | `InMemoryEmissionInterface.emit` / `OfflineArcadeEmissionInterface.emit` | authorized `EmissionResult` / rendered sample result |

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
Pure-LLM execution calls the OFFLINE adapter only with a capability-backed HDS
directive. The sample agent's direct action methods always reject.

## Required trace

```text
Arcade(OperationMode.OFFLINE)
rendered FrameDataRaw
FRAME / SYMBOL_SPACE
CONTEXT_STATE update
passive memory read
HDS compute command
Pure-LLM hypothesis/candidate proposal
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
- bundled sample observationをtask identity-free IRへ変換
- `OperationMode.OFFLINE`以外のP1起動を事前拒否
- modeラベルだけでなく`LocalEnvironmentWrapper`実体を要求
- HDS承認済みactionだけをlocal sample `step`へ放出
- ACTION6座標を現在frame寸法から動的に生成
- actual rendered effectsをcontextへ格納
- action後の再観測と次HDS判断
- 保持済み25ゲームすべての1-action / no-network smoke
- optional frame recordingとtrace / decision digestを含むJSON report
- current `arcengine` / `Arcade` APIに整合したrepository-wide unit harness
- optional agent dependencyを選択時まで読み込まないlazy import boundary
- `agents`と`arc3_agi_agent`を明示的に含むinstallable package

## Not closed in P1

- 全sample game / 全183 levelの攻略
- GAME_OVER、timeout、無限loop、max-action停止の全解消
- sample完全攻略の再現性・regression固定
- official API / competition connection
- Kaggle Notebook / CLI / MCP / submission
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

python -m unittest discover \
  -s ARC-AGI-3-Agents/tests/integration \
  -p "test_offline_sample_runner.py" \
  -v

python ARC-AGI-3-Agents/sample_main.py \
  --all-samples \
  --max-actions 1

# editable / wheel install後
arc3-p1-samples --all-samples --max-actions 1

ruff check \
  ARC-AGI-3-Agents/arc3_agi_agent \
  ARC-AGI-3-Agents/agents/__init__.py \
  ARC-AGI-3-Agents/agents/recorder.py \
  ARC-AGI-3-Agents/tests/conftest.py \
  ARC-AGI-3-Agents/tests/unit

git diff --check
```

2026-07-23のsample接続監査では、保持済み25ゲームを各1 actionだけ実行し、
25/25でHDS承認、OFFLINE step、再観測、context / memory更新、次HDS判断が
成立しました。全25件のrendered transition判定は、level progressを未観測のため
正規出力`SUSPEND`で、`FAIL`は0件です。integration testは
`requests.Session.request`を強制失敗させ、network利用がないことを同時に
検査します。

この結果はP1経路の証拠であり、P2のlevel攻略数へ加算しません。同一差分の
完了監査では、`unittest` 40件、`pytest` 96件（25-game integrationを含む）、
compile、ruff、`git diff --check`、isolated wheel buildがすべて通過しました。
wheelにはsample agent / runtime / adapter / CLIと`arc3-p1-samples` entry pointが
含まれます。
