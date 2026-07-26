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
| sample evidence | S5 183/183、authority audit、oracle、全10,733 cycle trace、二回byte一致 |
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

固定した再現性監査command:

```bash
python -m arc3_agi_agent.s5_runner \
  --environments-dir ../environment_files \
  --seed 0 --max-actions 4096 \
  --trace-jsonl \
    ../scratch/s5-full-trace-reproduction/S5_FULL_EXECUTION_TRACE.jsonl.gz \
  --trace-manifest \
    ../scratch/s5-full-trace-reproduction/S5_FULL_EXECUTION_TRACE_MANIFEST.json \
  --output \
    ../scratch/s5-full-trace-reproduction/S5_RENDERED_ONLY_CLOSURE_REPORT.json

arc3-audit-p10-reproducibility \
  --s5-primary ../analysis/runtime/S5_RENDERED_ONLY_CLOSURE_REPORT.json \
  --s5-reproduction \
    ../scratch/s5-full-trace-reproduction/S5_RENDERED_ONLY_CLOSURE_REPORT.json \
  --s5-trace-primary-manifest \
    ../analysis/runtime/S5_FULL_EXECUTION_TRACE_MANIFEST.json \
  --s5-trace-reproduction-manifest \
    ../scratch/s5-full-trace-reproduction/S5_FULL_EXECUTION_TRACE_MANIFEST.json \
  --s6-primary ../analysis/runtime/S6_PERTURBATION_MEASUREMENT.json \
  --s6-reproduction \
    ../scratch/s6-repro/S6_PERTURBATION_MEASUREMENT.json \
  --output ../analysis/release/P10_REPRODUCIBILITY_AUDIT.json
```

`S5_FULL_EXECUTION_TRACE.jsonl.gz`は全cycleのcanonical JSONLを
`mtime=0`のgzipへ格納する。manifest loaderは圧縮file SHA、record stream
digest、連番、kernel trace digest、game別closure trace digest、全183 levelの
coverageを再計算する。

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
analysis/runtime/S5_FULL_EXECUTION_TRACE.jsonl.gz
analysis/runtime/S5_FULL_EXECUTION_TRACE_MANIFEST.json
```

## 5. 非主張・禁止

- S6はresponse stability測定でありsemantic correctnessではない。
- 未知taskへの汎化は`MEASURED_NOT_PROVEN`。
- 公式ARC接続、`OperationMode.COMPETITION`、Kaggle、submissionは未実行。
- P12以降は本依頼のscope外であり、P11中に前倒ししない。

## 6. 固定結果

| 項目 | 固定値 |
|---|---|
| code commit | `823c51b68d7f1a2570a3c68f8f21a3819c650154` |
| code tree | `b3b675a24dcecd5080927c9bbf80c77eb7d083f5` |
| regression | 7/7 PASS |
| regression digest | `arc3_p11_regression_report:52b7e68c5314d91e2d7769458b6082d19f87778db5ba1dbf8c5d8cb24ebcef91` |
| P0 initial digest | `3b4330dff890310572abfadc42470f1549bb35c2ff351d007bc1557e99c70a62` |
| J0 initial digest | `2c87595b6ea7c415a9d09b5c5adabefaf2a9e3ad9e9bb339674f9c8c6de2d798` |
| M0 initial digest | `2c8c4194e7be89117eb1d39de6be98eab87fa5af6a0a6bd369e1fb2dca1a2aff` |
| sample ZIP SHA-256 | `c72400a32db5e48da9014baf893b48016b300e9a6a77bd5d505de2b1ec61d645` |
| wheel | `arc_agi_3_agents-0.1.0-py3-none-any.whl` |
| wheel reproducibility | 二回byte一致 |
| wheel SHA-256 | `a2f7c400753a553b49247ce7627e2b966fd152153b53064e7403e553659e551a` |
| release digest | `arc3_p11_release_state:e7d8ef522f8f0004a63875a7da3cdcc084684388325411a994e751d6e251eb8c` |

packageにはRuntime policy manifest/weightsを含み、S5 training corpus、
`analysis/`、`environment_files/`を含めない。公式環境readinessと未知task汎化は
この固定結果から主張しない。
