# P3 ARC3実証素材コンパイラ

- phase: `P3_ARC3_EVIDENCE_MATERIAL_COMPILER`
- status: `COMPLETE`
- HDS judgment: `PASS`
- next phase: `P4_COMPUTE_SUBJECT_C`
- compiler version: `arc3-evidence-compiler-v1`
- fixed seed: `0`

本書はP3の実装境界、生成物、実測値、再生成手順を固定する。P3が証明するのは
ARC3解析素材をidentity-free fixtureへ変換できることだけであり、P、C、J、M、
最小三構成、sample攻略、汎化を証明しない。

## 1. Work block

### X

- 読取り対象:
  - 旧repo `analysis/**/*.json`
  - current repo `environment_files/*/*/metadata.json`
- 変更対象:
  - `ARC-AGI-3-Agents/arc3_agi_agent/evidence_compiler.py`
  - `datasets/`
  - `manifests/`
  - P3 test / docs
- 非対象:
  - 旧repoの変更
  - environment Python sourceのruntime学習入力化
  - P-A/P-B、C/J/Mの実装
  - sample攻略、公式接続、Kaggle

### R

```text
source bytes
  -> SHA-256 / parse status / source index
  -> sensitive-key subtree rejection
  -> bounded semantic and structural extraction
  -> category-specific identity-free body
  -> source-neutral aggregation
  -> family / structure / action-mechanism split
  -> runtime corpus + runtime-forbidden provenance
```

全source bytesはhashとparse statusでaccountingする。正規化抽出は一sourceあたり
mapping 512要素、sequence 128要素、depth 24、signal 384件へ決定的に上限化する。
上限到達はprovenanceの`truncated_collection_count`へ残す。したがって
「全sourceをaccountingした」と主張するが、「全source内の全scalarをfixture化した」
とは主張しない。

### Mc

P3を`PASS`にする条件:

1. 全sourceが一意なindex、path、byte count、SHA-256、parse statusを持つ。
2. parse errorが0件である。
3. C/J/M fixture categoryが分離され、全categoryが空でない。
4. provenanceがsourceからrecord、recordからsourceへ往復できる。
5. runtime corpusにgame/task/level identity、replay、answer、固定列、literal座標、
   source state、source filenameがない。
6. family、structure、action-mechanism groupが一つのsplitだけへ属する。
7. 同じ入力・seed・compilerで全生成ファイルがbyte一致する。

いずれかが崩れた場合は`SUSPEND`し、P4へ進まない。

## 2. Source snapshot

旧repoはdirty working treeであり、commit SHAだけでは入力を再現できない。そのため
revision labelと、全source file hashから作るinventory digestを併記する。

| 項目 | 値 |
|---|---:|
| source revision label | `96f3d2deebc7c05c07e7c817f131a2a5136f5822+working-tree-content-manifest` |
| analysis JSON | 705 files / 246,942,536 bytes |
| environment metadata | 25 files / 7,525 bytes |
| total | 730 files |
| parse error | 0 |
| source inventory digest | `7f3afe283d53d6cc6d1486bdd5ef407cb2fb193d41cabd155c09189bca9192a7` |

旧repoへ書込みは行っていない。source identityとpathは
`manifests/provenance_manifest.json`だけに置き、同manifestは
`runtime_use: FORBIDDEN`である。

## 3. 生成物

```text
datasets/
  observations/records.jsonl
  transitions/records.jsonl
  effects/records.jsonl
  hazards/records.jsonl
  progress/records.jsonl
  contradictions/records.jsonl
  hds_frames/records.jsonl
  memory_lifecycles/records.jsonl
  holdout_families/manifest.json
manifests/
  dataset_manifest.json
  provenance_manifest.json
  identity_free_audit.json
```

| category | record count | fixture owner |
|---|---:|---|
| observations | 653 | C |
| transitions | 681 | C |
| effects | 638 | C |
| hazards | 583 | C |
| progress | 663 | C |
| contradictions | 466 | C |
| hds_frames | 676 | J |
| memory_lifecycles | 687 | M |
| total | 5,047 | separated C/J/M material |

25 metadata filesはgame identity、title、baseline action、local path等しか持たないため、
水平引き算後は`ACCOUNTED_NO_RUNTIME_MATERIAL`となる。705 analysis JSONはすべて
少なくとも一つのruntime recordへtraceされる。

## 4. 水平引き算

compilerは正規化keyに対して次を拒否する。

- game/task/level ID、task name、title
- replay / replay index / replay action
- answer / answer map
- baseline/fixed action sequence
- coordinate / literal coordinate
- source/hidden state
- filename/path/local directory/date

runtime outputは固定semantic vocabulary、数値bucket、frame dimension/palette bucket、
action class、support/confidenceだけを持つ。opaque runtime IDは10進数字だけで構成し、
game IDとhash substringが偶然一致する経路も除去した。

独立監査結果:

- current environment identity token: 75 checked / 0 leaked
- provenance source filename: 706 unique checked / 0 leaked
- forbidden runtime key: 0
- compiler identity audit forbidden path: 0

## 5. Holdout

seedは`0`に固定し、opaque group digestから次を決定する。

- game/source family: 70% train / 15% validation / 15% holdout
- structure family: 同上
- action-mechanism family: 同上
- layout/color/position perturbation: `required`

family groupとsource splitはprovenanceで照合する。structure/action-mechanism groupは
runtime recordのidentity-free `split_groups`とholdout manifestで照合する。
一つのgroupが複数splitへ入った場合、P3 validatorはFAILする。

## 6. 実装と試験

- compiler:
  `ARC-AGI-3-Agents/arc3_agi_agent/evidence_compiler.py`
- compiler unit:
  `ARC-AGI-3-Agents/tests/unit/test_evidence_compiler.py`
- generated dataset audit:
  `ARC-AGI-3-Agents/tests/unit/test_p3_evidence_dataset.py`

実行入口:

```bash
cd ARC-AGI-3-Agents
python -m arc3_agi_agent.evidence_compiler \
  --analysis-dir /path/to/legacy/analysis \
  --environment-dir ../environment_files \
  --output-dir ../datasets \
  --manifest-dir ../manifests \
  --source-revision "<commit>+working-tree-content-manifest"
```

実測gate:

- compiler / dataset audit: `14 passed`
- ruff: `All checks passed`
- strict mypy: `Success: no issues found`
- deterministic rebuild: 12/12 files byte-identical
- missing / extra / changed files: 0 / 0 / 0

## 7. P3 claim boundary

P3で`SUPPORTED`へ昇格するのは
`CLAIM_P3_EVIDENCE_COMPILER`だけである。

次は引き続き`UNSUPPORTED`または`PARTIAL`である。

- compilerからversioned P0/J0/M0を形成する能力
- executable P-A/P-B
- standalone C/J/M
- learned parameter bodyの実学習
- holdout上の汎化性能
- two-cycle experience causality
- minimum-three certificate
- all-sample completion
- release-state rebuild

P4はこのP3 datasetを入力候補として用いるが、provenance manifestをruntimeへ
渡してはならない。
