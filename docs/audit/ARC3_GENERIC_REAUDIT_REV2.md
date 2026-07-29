# ARC3 汎用自律完遂主体 再監査 rev2

- audit ID: `ARC3_GENERIC_REAUDIT_REV2`
- phase: `P16_CLAIM_THREAT_EVALUATION_REBASELINE`
- baseline commit: `baa03f3ba7648503d5d212d6afe9c956c56984fc`
- specification: `ARC3_GENERIC_AUTONOMOUS_COMPLETION_SPEC_REV2`
- roadmap: `P16_P24_GENERIC_AUTONOMOUS_COMPLETION_ROADMAP_REV2`
- audit date: `2026-07-30`
- runtime code change in P16: `NONE`
- conclusion: `P16_PASS_P17_A_NOT_STARTED`

> このconclusionはP16終了時点のsnapshotである。P17-Aはその後
> `docs/architecture/P17A_COGNITIVE_SESSION_STATE_OWNERSHIP.md`で
> 6/6 PASSとなった。P16 findingは発見時点の履歴として保持する。

## 1. Work Block

```text
X:
  対象 = claim、runtime path分類、identity/taint、evaluation role、
         official completion predicate、phase selector
  入力 = baseline commit、rev2仕様書、rev2ロードマップ、現行source/証拠
  変更範囲 = governance文書、machine registry、監査test

R:
  現行実装と証拠をrev2 claim hierarchyへ再分類し、
  各不足を最初に修正可能なphaseへ束縛する

Mc:
  同一性 = baseline tree上のpath/symbol/artifact digest
  境界 = P16。runtime behaviorは変更しない
  採否 = 実行証拠とscopeが一致するclaimだけ許可
  停止 = overclaim、複数active runtime、role重複、未定義official scope
  rollback = P16 governance差分だけを戻せる
  完了 = P16-001〜P16-006が全件PASS

非目的:
  CognitiveSession、共有M、atomic memory、causal promotion、P-IR、
  sealed final実行、Competition package、公式提出

証拠境界:
  current repositoryと提供rev2正本。外部scoreや記憶上の結果は採用しない

反証条件:
  progressをcompletionと表記する
  S5をactive generic fallbackとして扱う
  P12の複数artifact証拠をsingle-artifact完成へ合算する
  scoreなしrunをofficial acceptedと表記する

回帰線:
  P11/S5 historical artifact不変、HDS sole authority、
  Teacher/source/replay/identity routing禁止を維持
```

## 2. Runtime path inventory

| Path | 分類 | 許可用途 | 禁止用途 |
|---|---|---|---|
| `GenericAGIRuntime` + generic competition adapter | `ACTIVE_RECONSTRUCTION_TARGET` | P17以降でrev2へ段階再構成する唯一のactive path | 現状のままrev2完成claimを出すこと |
| `KnownSampleStudent` / S5 | `HISTORICAL_BASELINE` | P11 known-sample 183/183回帰 | active fallback、genericity、sealed/official claim |
| `teacher/` とS0〜S4 | `DEVELOPMENT_ONLY` | 歴史的閉包・構造抽出証拠 | runtime package、判断入力 |
| P10 game-specific/operator群 | `HISTORICAL_DEVELOPMENT` | 過去のnegative/closure監査 | active runtime、identity routing |
| rev1 sealed/CV artifacts | `HISTORICAL_CONSUMED` | 旧手順の補助証拠 | rev2 `LOCKED_FINAL`、single-artifact claim |

active runtime countは`1`である。runner、adapter、agent templateは
`GenericAGIRuntime`の境界部品であり、別runtimeとして数えない。

## 3. Claim correction

### 保持

- P11/S5の25 game・183 levelは`KNOWN_SAMPLE_HISTORICAL_CLOSURE`
- P9の最小三構成certificateは定義済みfixture範囲の構造証拠
- P12のC/J/M/P、mock、holdout、変換、sealed結果はrev1手順の歴史的証拠
- Kaggle通常Notebook実行は通常実行・packagingの歴史的preflight証拠

### 降格

| 旧表記 | rev2分類 | 理由 |
|---|---|---|
| `CLAIM_GENERICITY = SUPPORTED` | `HISTORICAL_ONLY` | whole-game holdout完了は0。progressだけではcompletionでない |
| `PRE_OFFICIAL_AGI_READY = SUPPORTED` | `HISTORICAL_ONLY` | rev1の57項目はrev2 blocking registryを満たさない |
| transformations `7/7 PASS` | `HISTORICAL_ONLY` | rev2は実environment completionを要求する |
| sealed `3/3 PASS` | `HISTORICAL_CONSUMED` | full completionでなく、既に内容・結果を開発側が保持する |
| Notebook `COMPLETE` | `PREFLIGHT_ONLY` | official hidden rerun accepted/scoreを意味しない |

### 現行claim

```text
STRUCTURAL_READY                    = NOT_ESTABLISHED
KNOWN_PUBLIC_REGRESSION             = NOT_EVALUATED_ON_ACTIVE_RUNTIME
MEMORY_CAUSAL                       = NOT_ESTABLISHED_REV2
P_VERSION_LEARNING_CAUSAL           = NOT_ESTABLISHED
CV_PROCEDURE_EVIDENCE               = NOT_EVALUATED_REV2
TRANSFORMATION_STRESS_PASS          = NOT_EVALUATED_REV2
SEALED_SINGLE_ARTIFACT_COMPLETE      = NOT_EVALUATED
COMPETITION_READY                   = NOT_ESTABLISHED
OFFICIAL_RUN_ACCEPTED               = NOT_OBSERVED
OFFICIAL_PUBLIC_COMPLETE            = NOT_OBSERVED
OFFICIAL_PRIVATE_COMPLETE           = NOT_OBSERVED
OFFICIAL_FULL_COMPLETE              = NOT_OBSERVED
```

`AGIがARC3を閉包した`という表記は禁止する。

## 4. Current implementation findings

| ID | Finding | Evidence | First correction phase |
|---|---|---|---|
| `F-P16-001` | runtimeがM/J/P/authorityを内部生成する | `generic_runtime.py::GenericAGIRuntime.__post_init__` | P17-A |
| `F-P16-002` | scorecardごとでなくgameごとにagent/runtimeが生成される | `generic_competition_runner.py`, `generic_agi_agent.py` | P17-A |
| `F-P16-003` | HDSがworld-learning selector stateをprivate保持する | `_selector_deltas`, `_value_actions` | P17-A |
| `F-P16-004` | unrelated M recordでも`has_memory_evidence`が成立し得る | `generic_hds.py::judge` | P17-B |
| `F-P16-005` | candidate provenance intersectionが空でもglobal evidenceでreproducedになる | `or has_memory_evidence` | P17-B |
| `F-P16-006` | semantic keyがsurface ordinalをcross-context keyへ含む | `surface:{ordinal}` | P17-B/P19 |
| `F-P16-007` | live memoryを先に変更し、失敗時atomic rollbackがない | `generic_memory.py::apply_authorized` | P18 |
| `F-P16-008` | versionごとのfull-copy snapshotを保持する | `_snapshots[next_version] = dict(...)` | P18 |
| `F-P16-009` | causal precondition/effect/scopeと独立episode支持が未型付け | current `SemanticRecord` | P19 |
| `F-P16-010` | representation/candidate生成が固定PythonでP-IRではない | `generic_compute.py` | P20-A |
| `F-P16-011` | compilerは固定L0上のrepresentation交換を生成しない | `generic_learning.py` | P20-B |
| `F-P16-012` | role/access/consumed stateの正本がなかった | evaluation artifacts | P16で文書是正、P21で実行台帳 |
| `F-P16-013` | Public/Private/fullの完成述語が分離されていなかった | rev1 claim/README | P16で是正 |

P16は不足を隠さない。`F-P16-001`〜`F-P16-011`は後続phaseのblocking inputであり、
文書化したことを実装完了とは数えない。

## 5. P16 gate

| Gate | Result | Evidence |
|---|---|---|
| `P16-001 claim_overstatement = 0` | `PASS` | claim registryと本監査のscope訂正 |
| `P16-002 active_runtime_count = 1` | `PASS` | `control/p16/P16_PHASE_STATE.json` |
| `P16-003 evaluation_role_registry` | `PASS` | evaluation role spec/registry |
| `P16-004 identity_taint_threat_model` | `PASS` | threat model |
| `P16-005 completion_predicates` | `PASS` | official predicates |
| `P16-006 rev1_status` | `HISTORICAL_NON_BLOCKING` | rev1文書bannerとauthority順序 |

P16の`PASS`はgovernance rebaselineだけを意味する。次に許可されるwork blockは
P17-Aのcontainer/state ownershipであり、P17-B以降は未開始である。
