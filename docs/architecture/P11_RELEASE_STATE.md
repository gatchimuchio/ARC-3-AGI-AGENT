# P11 Release-state Freeze

- phase: `P11_RELEASE_STATE_FREEZE`
- state: `IN_PROGRESS`
- predecessor: `P10_COMPLETE_ARC3_SAMPLE_SOLVING`
- operation mode: `OFFLINE`
- successor: `P12_OFFICIAL_ARC_CONNECTION`
- successor status: `NOT_STARTED_CURRENT_REQUEST_OUT_OF_SCOPE`

## 1. 固定式

```text
Release State
= P0 + J0 + M0 + code + dependency + environment
```

本phaseはRuntime能力やscoreを変更しない。P10で閉じたS5 Runtime PとS6測定を
同一code tree、dependency、初期状態、実行条件、packageへ固定する。

## 2. 固定対象

| 対象 | 固定値・証拠 |
|---|---|
| code | `main`のcommit SHAとtree SHA |
| dependency | `pyproject.toml`、`uv.lock`、導入version |
| Python | `3.12.13`、`.python-version` |
| P0 | `s5-rendered-history-mlp-v1` manifest、weights、digest |
| J0 | HDS Frame policy、purpose、boundary、stop、rollback、空controller state |
| M0 | version 0、active/archive 0、max entry 1、history snapshot 3 |
| dataset | P3 manifest/audit、S5 corpus manifest/NPZ |
| compiler | S5 corpus/policy、structure、S6、P11 compiler source digest |
| seed | Runtime 0、action head ordinal、pointer 41/43、PYTHONHASHSEED 0 |
| action budget | 4,096 per environment |
| regression | compileall、ruff、strict mypy、全unit、全integration、diff、secret scan |
| sample evidence | S5 183/183、authority audit、oracle、二回byte一致 |
| S6 evidence | 七摂動14,336件、二回byte一致、`MEASURED_NOT_PROVEN` |
| package | fixed epochでwheel二回build、byte一致、内容・digest監査 |

## 3. 初期状態境界

### P0

P0は`arc3_agi_agent/bundles/s5_rendered_policy_v1.{json,npz}`である。
Runtime入力はrendered observation、available action、bounded action/effect
history、HDS承認済み受動Mだけとする。training example、render hash lookup、
fixed action sequence、literal coordinate table、game/task/level routing、
source/hidden stateを含めない。

### J0

fresh `HDSController`、`HDSOutcomeRetentionController`、
`HDSPolicyResetController`とversioned `HDSFramePolicy`を初期状態とする。
command、decision、binding、directive、emission、retention、resetの各countは0。
HDSだけがcommand、採否、停止、rollback、memory、reset、external emissionを
許可する。

### M0

fresh `PassiveMemory(max_entries=1, max_history_snapshots=3)`を使用する。
version 0、active/archive/provenance 0、retained snapshot versionは`[0]`。
task/game/level identityを初期memoryへ入れない。

## 4. 検証順序

```text
P10 S5/S6 exact rerun audit
  -> implementation/static/unit/integration regression
  -> code commit/tree固定
  -> fixed-epoch wheelを二回build
  -> package byte/content audit
  -> P0/J0/M0と全証拠をrelease manifestへ束縛
  -> release manifest test
```

正本成果物:

```text
analysis/release/P10_REPRODUCIBILITY_AUDIT.json
analysis/release/P11_REGRESSION_REPORT.json
analysis/release/P11_RELEASE_STATE.json
```

## 5. 非主張・禁止

- S6はresponse stability測定でありsemantic correctnessではない。
- 未知taskへの汎化は`MEASURED_NOT_PROVEN`。
- 公式ARC接続、`OperationMode.COMPETITION`、Kaggle、submissionは未実行。
- P12以降は本依頼のscope外であり、P11中に前倒ししない。
