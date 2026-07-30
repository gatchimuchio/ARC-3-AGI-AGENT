# HDS蒸留開発ロードマップ ARC2／ARC3 rev2

**対象：正解付きARC素材の機構蒸留のみ**

| 項目 | 内容 |
|---|---|
| 最終採否 | 大平鉄兵 |
| 実装主体 | Codex |
| 版 | rev2 |
| 日付 | 2026-07-30 |
| 依存仕様 | `HDS蒸留仕様書_ARC2_ARC3_rev2.md` |
| 状態 | rev1監査指摘反映済み・順序付き実装ロードマップ |
| Scope | 蒸留pipelineと静的成果物freezeのみ |

---

# 0. Codex運用契約

## 0.1 最上位目的

```text
正解付き教師素材
→ 実行可能機構候補
→ exact fit
→ 教師拘束内counterfactual
→ HDS判断
→ 横断規則・境界・反例・FailureSignature
→ 静的freeze
```

## 0.2 禁止

- 未知taskを解かない
- solver／agentを作らない
- production runtimeへ接続しない
- RAG／検索／活用層を作らない
- official APIを呼ばない
- source codeから答えを直接抽出しない
- task／game identityでroutingしない
- fixed answer／action sequenceをRuleAtom化しない
- Phaseを飛ばさない
- blocking gate未通過で次Phaseへ進まない
- 未固定事項を自己判断で埋めない

## 0.3 Phase／Gate命名

```text
Phase: PH-Dxx
Gate:  DG-xx
```

`D05`のような衝突表記を使用しない。

---

# 1. 全体依存順序

```text
PH-D00A  HDS Dependency / Authority Freeze
  ↓
PH-D00B  Scope / Repository Bootstrap
  ↓
PH-D01A  Source Dialect / Contamination Inventory
  ↓
PH-D01B  Content / Acquisition / Environment Manifests
  ↓
PH-D02A  Canonical Serialization / Digest
  ↓
PH-D02B  Evidence / HDS State / Approval Schemas
  ↓
PH-D02C  Typed Causal IR / Interpreter / Verifier ABI
  ↓
PH-D03A  Golden Conformance Corpus
  ↓
PH-D03B  Sealed Audit Corpus / Approval Freeze
  ↓
PH-D04   ARC2 Observation and Derivation
  ↓
PH-D05   ARC3 Raw Teacher Trajectory Normalization
  ↓
PH-D06   Hypothesis Candidate Generation / LLM Capture
  ↓
PH-D07A  Extensional Exact-Fit Verification
  ↓
PH-D07B  Counterfactual Intervention Verification
  ↓
PH-D08   Per-Case HDS Decision Record
  ↓
PH-D09   Normalization / Rewrite Certificates
  ↓
PH-D10   Cross-Case Commonality Extraction
  ↓
PH-D11   Boundary / Negative / Counterexample Audit
  ↓
PH-D12   Evidence-Graded Promotion / Owner Approval
  ↓
PH-D13   Frozen-Input Deterministic Rebuild x3
  ↓
PH-D14   Coverage / Completion States / Artifact Freeze
```

PH-D02BとPH-D02CがPASSするまで、schema freezeとGolden期待値freezeを行わない。

---

# PH-D00A — HDS Dependency／Authority Freeze

## 目的

HDS正本、Translator参照版、権威順序、最終採否者をcontent digestで固定する。

## 実装

- HDS三資料のSHA-256再計算
- Translator commit `b501cc77c94048421af8efdb2e866c22b06f7208`を固定
- `DEPENDENCY_LOCK.md`
- `AUTHORITY_ORDER.md`
- dependency mismatch時のfail-closed
- Open Term Ledger初期化

## 成果物

```text
DEPENDENCY_LOCK.md
artifacts/source_content_manifests/hds_dependencies.json
artifacts/reports/dependency_audit.json
```

## Gate

- `DG-00`
- `DG-14`

## DoD

```text
hds_dependency_match = true
authority_defined = true
unresolved_dependency_count = 0
```

不一致時は全工程`SUSPEND`。

---

# PH-D00B — Scope／Repository Bootstrap

## 目的

蒸留専用repositoryを構築し、活用能力の混入をbehaviorで禁止する。

## 実装

- repository skeleton
- `SCOPE_LOCK.md`
- Python 3.12系環境固定
- formatter／type checker／test runner
- input／schemas／src／tests／artifacts分離
- AST／import graph／entrypoint scope audit
- official API、network、submission outputの禁止試験
- offline interpreter／teacher replayは明示許可

## 禁止

filename blacklistだけでscopeを判定しない。

## Gate

- `DG-02`
- `DG-09`
- `DG-14`

## DoD

- 正当なoffline interpreterがscope guardを通る
- official API callableを追加するとCI FAIL
- unlabeled task answer callableを追加するとCI FAIL
- submission artifact generatorを追加するとCI FAIL

---

# PH-D01A — Source Dialect／Contamination Inventory

## 目的

ARC2／3素材を、配布形式、split、answer visibility、利用目的、汚染状態で分類する。

## 実装

### ARC2 profile

- `ARC2_KAGGLE_CHALLENGE_SOLUTION`
- `ARC2_OFFICIAL_TASK_JSON`
- `ARC2_INTERNAL_NORMALIZED_CORPUS`

### ARC3 profile

- `ARC3_ENVIRONMENT_SOURCE_BUNDLE`
- `ARC3_RAW_TEACHER_RECORDING`
- `ARC3_CANONICAL_TEACHER_TRAJECTORY`

### 分類

```text
TRAIN_TEACHER
PUBLIC_EVALUATION_TEACHER
PUBLIC_EVALUATION_CONSUMED
UNLABELED_TEST
REPLAY_ONLY_SOURCE
SEALED_AUDIT
```

## 成果物

```text
profiles/source/*.json
artifacts/reports/source_inventory.json
```

## Gate

- `DG-00`
- `DG-06`
- `DG-09`

## DoD

- 全source fileが一つのprofileへ分類
- answer visibility不明0
- split role不明0
- evaluation解答使用時のcontamination明示

---

# PH-D01B — Content／Acquisition／Environment Manifest

## 目的

内容同一性、取得記録、実行環境を分離して凍結する。

## 実装

- `SourceContentManifest`
- `AcquisitionRecord`
- `EnvironmentManifest`
- `RunManifest`
- repository-relative POSIX path
- directory Merkle root
- ARC3 wheel hash
- Python／OS／dependency lock
- source read-only
- environment isolation report

## Gate

- `DG-00`
- `DG-06`
- `DG-12`

## DoD

- 同一内容を別path／別時刻で取得してもcontent digest一致
- mtime／created_at変更でcontent digest不変
- source改変でdownstream invalidation
- ARC3 replay environment hash完全

---

# PH-D02A — Canonical Serialization／Digest

## 目的

全schema共通の決定論的表現を先に固定する。

## 実装

- canonical JSON
- Unicode NFC
- confidence_ppm
- ID生成規則
- digest field除外規則
- logical／physical digest分離
- canonical NPZ／ZIP packaging
- raw／canonical trajectory digest分離
- test vectors

## Gate

- `DG-06`
- `DG-07`

## DoD

- Python process／path／timeを変えてlogical digest一致
- NaN／Infを拒否
- unordered inputを正規化
- canonical test vector x3一致

---

# PH-D02B — Schema／HDS State／Approval

## 目的

38 schemaを相互参照可能な形で固定する。

## 実装

仕様書第8章の全schema。

特に次を先に閉じる。

- DependencyLock／SourceProfile／ResourceProfile／OperatorRegistry
- RawObservation
- DeterministicDerivation
- InterpretationHypothesis
- DistillationFrame
- ModelRecord
- DecisionRecord
- HDSCausalRecord
- PromotionDecision
- ApprovalRecord
- OpenTermRecord／ClaimRecord
- CoverageReport／CompletionStateRegistry

## 必須状態軸

```text
assertion_state
operation_state
adoption_state
evidence_state
mechanism_support_state
closure_state
update_state
```

## Gate

- `DG-00`
- `DG-01`
- `DG-02`
- `DG-14`

## DoD

- schema一覧とdirectory 1対1
- 全例にversion／digest
- MULTI_CAUSAL／SUSPENDで単一choice不要
- inferred evidence混入例をreject
- initial RuleAtomはPROPOSED／PROBATIONのみ
- invalid reference IDをreject

---

# PH-D02C — Typed Causal IR／Interpreter／Verifier ABI

## 目的

機構候補を実行・比較・canonicalizeできる型付き言語として固定する。

## 実装

- common type system
- ARC2 opcode registry
- ARC3 opcode registry
- Operator Registry Entry契約
- HypothesisIR schema
- pure deterministic interpreter
- type checker
- selector cardinality semantics
- cost model
- invalid operation semantics
- unknown opcode rejection
- Code／IR ABI
- answer-copy／identity linter
- exact comparator interface
- intervention runner interface

## Gate

- `DG-03`
- `DG-08`
- `DG-09`
- `DG-12`

## DoD

- valid IRが実行可能
- type mismatchが明示FAIL
- unknown opcodeが明示FAIL
- full answer literal／case routingがFAIL
- operator orderを無断変更しない
- resource超過がSUSPEND
- interpreter x3 digest一致

PH-D02C未完了でPH-D03へ進まない。

---

# PH-D03A — Golden Conformance Corpus

## 目的

実装適合性を人間監査可能な少数caseで固定する。

## 選定

ARC2：

- recolor
- object selection
- translation／copy
- symmetry
- count／relation
- composite transform
- ambiguous multi-causal case
- impossible／unsupported opcode case

ARC3：

- simple action effect
- ACTION6 payload
- order-observed
- delayed effect
- GAME_OVER／reset
- ambiguous mechanism
- counterfactual-supported case
- resource suspension case

## 成果物

各case：

- raw observation
- deterministic derivation
- multiple HypothesisIR
- exact fit result
- intervention plan／result
- HDS record
- expected failure signatures
- ApprovalRecord

## Gate

全`DG-00`〜`DG-15`の最低一件ずつをcover。

## DoD

- Goldenは実装適合テストであり一般性証拠と表記しない
- 期待値変更は新ApprovalRecord必須
- Codexが自動更新できない

---

# PH-D03B — Sealed Audit Corpus

## 目的

実装者が期待値を開発中に変更できない監査入力を用意する。

## 実装

- frozen input digest
- expected artifact digestをOwner側で隔離
- test runnerはPASS／FAILだけ返す
- failure時に期待値本文を自動開示しない
- 一度使用したsealed corpusはversionを消費扱い

## Gate

- `DG-06`
- `DG-14`

## DoD

- source／expected artifactのdigest固定
- 実装コードからexpected内容を参照不能
- GoldenとSealedを混同しない

---

# PH-D04 — ARC2 Raw Observation／Deterministic Derivation

## 目的

ARC2問題・正解から、観測事実と決定的導出を生成する。

## 実装

### RawObservation

- dimensions
- raw input／output grid
- cell values
- pair／task provenance

### DeterministicDerivation

- cell delta
- color histogram
- connected components（4／8近傍を別algorithm ID）
- bounding boxes
- exact shape signatures
- preserved／changed／added／removed cell sets
- relation candidatesの材料

### InterpretationHypothesisへ送るもの

- object candidate
- movement candidate
- copied structure
- symmetry role
- causal target

## Gate

- `DG-00`
- `DG-06`
- `DG-09`

## DoD

- direct／computed／inferredを型で分離
- 全deltaがsource pointerを持つ
- algorithm config完全
- Golden一致
- x3 digest一致

---

# PH-D05 — ARC3 Raw Teacher Trajectory Normalization

## 目的

既知成功行動列を、公式ACTION契約に合うcanonical trajectoryへ変換する。

## 実装

- ACTION1〜ACTION7／RESET
- ACTION6 x／y payload
- available actions before／after
- raw／canonical frame
- terminal／level index／progress
- seed／reset mode
- source／wheel／environment digest
- raw recording／canonical trajectory digest
- exact replay verification
- sandbox isolation

## 禁止

- `UP`等をraw actionとして保存
- source codeをcandidate generatorへ渡す
- 成功軌道一回からnecessity／irreversibility／order requirementを断定

## Gate

- `DG-00`
- `DG-06`
- `DG-10`
- `DG-11`
- `DG-12`

## DoD

- 既知成功軌道を3回exact replay
- canonical trajectory digest一致
- 全stepがbefore／action／afterを持つ
- ACTION6 payload完全
- 可変metadataがcanonical hashへ入らない
- replay source access boundary PASS

---

# PH-D06 — Hypothesis Candidate Generation／LLM Capture

## 目的

各Teacher Caseから複数のHypothesisIR候補をboundedに生成する。

## 実装

- deterministic template generator
- bounded graph enumeration
- baseline／alternative／counter／null／overfit／surface／answer-copy adversarial
- ARC3 delayed／different goal候補
- candidate budget
- candidate provenance
- Alternative Adequacy計測
- selector family／operator familyの独立競合候補
- optional LLM capture

## LLM使用時

```text
prompt freeze
→ raw response capture
→ response digest
→ capture freeze
→ deterministic parse
```

## Gate

- `DG-03`
- `DG-04`
- `DG-05`
- `DG-08`
- `DG-12`

## DoD

- 一候補即採用なし
- non-strawman alternativeを最低2件
- answer-copy adversarialを生成しDG-08で棄却
- live LLMなしで後続再構築可能
- budget超過SUSPEND

---

# PH-D07A — Extensional Exact-Fit Verification

## 目的

候補が観測教師素材を正確に再現するか測定する。

## ARC2

- 全train pair exact output
- shape／cell mismatch
- extra／missing change
- task内leave-one-pair analysis（証拠として別記）

## ARC3

- step precondition
- raw action match
- predicted effect
- transition
- order observation
- terminal contribution prediction

## Gate

- `DG-07`
- `DG-08`
- `DG-09`

## DoD

- exact fitとcausal supportを別field
- fit失敗candidateはFALSIFIED
- exact fit candidateは最大LOCAL_EXACT_FIT
- answer lookup candidateはfitしても棄却
- comparator x3一致

---

# PH-D07B — Counterfactual Intervention Verification

## 目的

観測適合候補へ教師拘束内介入を行い、必要性・順序・境界の証拠を追加する。

## ARC2

- REMOVE_OPERATOR
- REPLACE_SELECTOR
- PERTURB_PARAMETER
- SWAP_OPERATOR_ORDER
- REMOVE_PRECONDITION
- REPLACE_STOP_CONDITION

## ARC3

- DELETE_STEP
- REPEAT_STEP
- SWAP_ADJACENT
- SUBSTITUTE_ACTION
- PERTURB_ACTION_PAYLOAD
- REPLAY_PREFIX_THEN_ALTERNATIVE
- REPLAY_WITH_SEED_VARIATION

## 実行規律

- planを実行前freeze
- adaptive search禁止
- available action外を要求しない
- budget内
- sandbox
- all outcomes保存
- 競合候補間で予測が分岐する介入を優先

## Gate

- `DG-06`
- `DG-10`
- `DG-11`
- `DG-12`

## DoD

- intervention未実施属性を断定しない
- plan／result／environment digestが結合
- failure／no-effect／delayed／WINを区別
- candidate固有FalsificationProcedureと対応
- 少なくとも一候補を棄却または明確に弱める
- counterfactual support levelを機械算出
- x3 repeatで同一結果、または非決定性を明示SUSPEND

---

# PH-D08 — Per-Case HDS Decision Record

## 目的

各caseをF／Md／Cm／Uへ正式に射影する。

## 実装

- DistillationFrame
- ModelSet
- DG-00〜DG-15
- DecisionRecord
- HDSCausalRecord
- Outcome／Attribution
- FailureSignature
- Open Term
- Update proposal

## Gate

全Gate。

## DoD

- X／R／Mc固定
- 複数Model保持
- selected／held／rejected分離
- 独立状態軸完全
- CLOSED_WITHIN境界あり
- Uはproposalまで、auto promotionなし
- HDS Run Conformance report PASS

---

# PH-D09 — Normalization／Rewrite Certificate

## 目的

事例差を削る処理と、新しい意味の一般化を分離する。

## 実装

- LOSSLESS_NORMALIZATION
- SEMANTIC_REWRITE
- GENERALIZATION_CANDIDATE
- inverse mapping
- assumptions
- equivalence evidence
- information loss
- operator commutativity registry

## Gate

- `DG-06`
- `DG-08`
- `DG-09`
- `DG-11`

## DoD

- losslessは逆写像PASS
- semantic rewriteはcertificate必須
- generalization candidateをactive ruleとして扱わない
- `3回`を`until boundary`へ無断変換しない
- ARC2／ARC3 cross-domain merge 0

---

# PH-D10 — Cross-Case Commonality Extraction

## 目的

canonical HypothesisIRからtyped common mechanismを抽出する。

## 実装

- type-preserving graph unification
- variable binding
- trigger／precondition／effect／exclusion分離
- support selection method
- independent case definition
- graph size／timeout／memory limit
- unresolved merge SUSPEND

## Gate

- `DG-03`
- `DG-06`
- `DG-12`
- `DG-13`

## DoD

- support setの後付け選択なし
- source caseからRuleAtomへ全provenance
- unsupported operator mergeなし
- timeoutでSUSPEND
- commonality report x3一致

---

# PH-D11 — Boundary／Negative／Counterexample Audit

## 目的

Rule候補の成立条件と不成立条件を独立素材で監査する。

## 実装

- predeclared negative pool
- near-miss mining
- counterexample mining
- boundary record
- alternative adequacy
- surface correlation audit
- answer-copy／identity audit
- failure signature aggregation

## Gate

- `DG-04`
- `DG-05`
- `DG-06`
- `DG-08`
- `DG-13`

## DoD

- strawman一件だけでpromotion不可
- negative pool定義あり
- support／near-miss／counterexample分離
- boundary未観測ruleはその旨を明示
- FailureSignatureがHDS全fieldを持つ

---

# PH-D12 — Evidence-Graded Promotion／Owner Approval

## 目的

RuleAtom／RuleFamilyを証拠強度に応じて昇格し、Owner採否を凍結する。

## 昇格順

```text
SUPPORTED_SINGLE
→ LOCAL_FIT
→ STRUCTURAL_RECURRENCE
→ BOUNDARY_OBSERVED
→ COUNTERFACTUAL_SUPPORTED
→ PROMOTED_CORPUS_SCOPED
→ REPRODUCIBLE_CONTROL
```

## 実装

- PromotionDecision
- valid scope
- evidence state
- support selection
- negative pool
- alternative adequacy
- intervention coverage
- identity audit
- Owner ApprovalRecord
- rollback／rejection

## Gate

- `DG-06`
- `DG-14`
- `DG-15`

## DoD

- auto promotion 0
- ApprovalRecordなしACTIVE 0
- corpus scope明記
- RuleAtom初期状態PROPOSED／PROBATION
- rejected candidateも台帳保持
- ARC2／ARC3 RuleFamilyを直接統合しない

---

# PH-D13 — Frozen-Input Deterministic Rebuild x3

## 目的

live LLM／live人間判断を排除し、凍結入力だけで成果物を再構築する。

## 入力

- source manifests
- environment manifests
- schemas
- operator registry
- frozen LLM captures
- ApprovalRecords
- resource profiles
- canonical code commit

## 実行

独立processで3回。

## Gate

- `DG-00`
- `DG-06`
- `DG-12`
- `DG-14`

## DoD

- logical digest全件一致
- CoverageReport一致
- RuleAtom／Family一致
- FailureSignature一致
- physical package canonical化後一致
- live external decision count 0

---

# PH-D14 — Coverage／Completion／Artifact Freeze

## 目的

pipeline完了、corpus処理、蒸留coverage、ruleset、Owner採否、freezeを分離して終了する。

## 生成

- `CoverageReport`
- `DistillationAudit`
- `FrozenArtifactManifest`
- open term ledger
- claim ledger
- completion state registry

## Completion State

```text
PIPELINE_IMPLEMENTATION_COMPLETE
CORPUS_PROCESSING_COMPLETE
CAUSAL_ASSET_COVERAGE_REPORTED
PROMOTED_RULESET_AVAILABLE
DISTILLATION_COVERAGE_ACCEPTED
FROZEN_ARTIFACT_COMPLETE
```

## Gate

- `DG-02`
- `DG-06`
- `DG-09`
- `DG-14`
- `DG-15`

## DoD

- 全source case accounting
- coverage count完全
- SUSPEND／PARTIAL／MULTIを隠さない
- Ownerがcoverageを採否
- exact inputから再構築可能
- 最終宣言がcorpus／DSL／介入境界付き
- 利用層実装0
- END

---

# 2. Gate通過条件の要約

| Gate | 主なblocking条件 |
|---|---|
| `DG-00` | dependency、frame、version不整合 |
| `DG-01` | 未定義語・未固定参照 |
| `DG-02` | scope／X／R／Mc未閉包 |
| `DG-03` | IR非実行、型不整合 |
| `DG-04` | counter hypothesisなし |
| `DG-05` | strawmanのみ |
| `DG-06` | provenance、証拠状態、再現性不足 |
| `DG-07` | exact fit不成立 |
| `DG-08` | tautology、answer copy、identity routing |
| `DG-09` | exact fitを真因と誤投影 |
| `DG-10` | unsafe／unbounded intervention |
| `DG-11` | 順序・遅延・帰属未検証 |
| `DG-12` | resource超過 |
| `DG-13` | surface correlation未反証 |
| `DG-14` | authority／approval欠損 |
| `DG-15` | promotion条件不足 |

---

# 3. 実装可能範囲

rev2確定後、次の順で開始する。

```text
即時開始可:
  PH-D00A
  PH-D00B
  PH-D01A
  PH-D01B

PH-D02A PASS後:
  PH-D02B

PH-D02B PASS後:
  PH-D02C

PH-D02C PASS前:
  Golden freeze、candidate generation、corpus処理は禁止
```

---

# 4. Codex初回Work Block

```text
目的:
HDS蒸留仕様書 rev2のPH-D00Aだけを実装する。

読む順序:
1. HDS蒸留仕様書_ARC2_ARC3_rev2.md
2. HDS蒸留開発ロードマップ_ARC2_ARC3_rev2.md
3. HDSフレーム_rev3_1a_内部用統合仕様.md
4. HDSフレーム_rev3_1_外向け仕様.md
5. HDS-BlackBox-Translator README

実施:
- HDS三資料のSHA-256を再計算
- Translator commitを固定
- DEPENDENCY_LOCK.mdを作成
- AUTHORITY_ORDER.mdを作成
- dependency manifest schemaの最小版を作成
- mismatch fail-closed testを作成
- Open Term Ledger初期schemaだけを作成

禁止:
- PH-D00B以降へ進まない
- ARCデータを処理しない
- Causal IRを先回り実装しない
- solver、agent、runtime utilizationを作らない
- 未固定事項を補完しない

終了条件:
PH-D00Aの成果物、テスト結果、未閉包項目、次Phase開始可否を報告して停止する。
```

---

# 5. 最終固定方針

本ロードマップは、

> **正解適合型パターン抽出を、因果蒸留と誤称しない。**

実行可能HypothesisIR、exact fit、教師拘束内介入、HDS状態分離、証拠強度、Owner採否、決定論freezeを順に閉じる。

PH-D14終了後も、蒸留成果物の活用方法は実装しない。
