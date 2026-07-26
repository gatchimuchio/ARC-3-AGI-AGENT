# P11 Release-state Freeze

- phase: `P11_RELEASE_STATE_FREEZE`
- state: `COMPLETE`
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
| package | `uv 0.11.32`、`setuptools 83.0.0`、fixed epochでwheel二回build、byte一致、内容・digest監査 |

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

WSLからWindows版`uv.exe`を実行する固定build command:

```bash
SOURCE_DATE_EPOCH=946684800 \
WSLENV=SOURCE_DATE_EPOCH \
uv.exe build --wheel --out-dir <output>
```

`WSLENV`を省くと`SOURCE_DATE_EPOCH`はWindows processへ伝播しないため、
同一commandとは扱わない。build backendは`setuptools==83.0.0`へ固定する。

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

## 6. 固定結果

| 項目 | 固定値 |
|---|---|
| code commit | `dca7be72c82389334ed2c3d585ec3c90c2b53914` |
| code tree | `a62902ca3f7b11bc8ba36d52e533d2142a405b30` |
| regression | 7/7 PASS |
| regression digest | `arc3_p11_regression_report:f93d72be7de8982bff0002671d505e3e234809b5aeb90853283eaa0654f92b75` |
| P0 initial digest | `3b4330dff890310572abfadc42470f1549bb35c2ff351d007bc1557e99c70a62` |
| J0 initial digest | `2c87595b6ea7c415a9d09b5c5adabefaf2a9e3ad9e9bb339674f9c8c6de2d798` |
| M0 initial digest | `2c8c4194e7be89117eb1d39de6be98eab87fa5af6a0a6bd369e1fb2dca1a2aff` |
| sample ZIP SHA-256 | `c72400a32db5e48da9014baf893b48016b300e9a6a77bd5d505de2b1ec61d645` |
| wheel | `arc_agi_3_agents-0.1.0-py3-none-any.whl` |
| wheel reproducibility | 二回byte一致 |
| wheel SHA-256 | `79a5c0de76efb795bb6025e5fd434f6ce25acc472f76c0d4bb543fd2122699d6` |
| release digest | `arc3_p11_release_state:70ffdd4395d0f50b312c002b226bd8c92ec1818597e913a72310dd1739177848` |

packageにはRuntime policy manifest/weightsを含み、S5 training corpus、
`analysis/`、`environment_files/`を含めない。公式環境readinessと未知task汎化は
この固定結果から主張しない。
