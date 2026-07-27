# AGI最小三構成 機能仕様

- specification: `AGI_MINIMUM_THREE_SPEC`
- version: `1.0.0`
- roadmap phase: `P12_PRE_OFFICIAL_AGI_CONFORMANCE_AND_GENERICITY`
- proof domain: ARC3を有限・観測可能な実証基盤として用いる機能的AGI
- normative roadmap: `docs/roadmap/AGI_MINIMUM_THREE_IMPLEMENTATION_PROOF_ROADMAP.md`

## 1. 定義域

本仕様が対象とするAGIは、次の五義務を同一実行系で満たす機能クラスである。

| ID | 義務 | 必須結果 |
|---|---|---|
| `G1` | 計算義務 | 現在観測に内容依存した表現、関係、仮説、反対仮説、予測、候補、更新案、出力案を生成する |
| `G2` | 判断義務 | 目的、証拠、リスク、境界、未閉包に基づき採否、再観測、SUSPEND、STOP、rollback、write/emit許可を決定する |
| `G3` | 保持義務 | 経験、仮説、反証、失敗、判断根拠を追加・改訂・統合・分割・置換・無効化・削除・再索引・rollback・archiveできる |
| `G4` | 時間因果義務 | cycle 1の経験によるM更新がcycle 2のC計算またはJ判断を実際に変える |
| `G5` | 閉ループ義務 | 計算、判断、行動、結果観測、記憶更新、再判断が権限境界を維持して閉じる |

ARC3のscoreや全level完了数は能力評価であり、`G1`〜`G5`の責任境界を代替しない。

## 2. 最小三主体

```text
C = Execute(L0, P)

AGI Kernel = Trinity(C, J, M)
```

### 2.1 計算主体 `C`

`C`はLayer-0実行機構`L0`が命令形保持体`P`を実行したときに成立する。

入力:

- HDSが発行したcompute request
- identity-free Observation
- bounded Context
- 明示的に引用されたM view（空でもよい）
- versionとdigestが確定したP

出力:

- representations
- hypotheses / counter-hypotheses
- predictions
- candidates
- memory update proposals
- output proposals
- uncertainty
- provenance

固有責任:

- 新しい計算素材の生成
- Pのaddressable領域の参照・選択・合成
- HDS承認済みwrite / emitの機械的実行

禁止:

- 候補の最終採用
- memoryの確定更新開始
- external emitの独断実行
- 自分の出力の真認定
- HDSDecisionの生成

### 2.2 判断主体 `J`

`J`はHDS Frameを閉包し、計算命令、採否、停止、rollback、write/emit許可を決める唯一主体である。

入力:

- purpose
- `X`
- `R`
- `Mc`
- observation boundary
- candidates / predictions
- evidence / counter-evidence
- risk / hazard / budget / unknowns

出力:

- compute request
- accept / reject / reobserve
- `SUSPEND` / `STOP` / `ROLLBACK`
- memory-write authorization
- external-emit authorization

禁止:

- 仮説または候補の生成
- memoryへの実書込み
- external actionの実行
- Pの計算代行
- Mの保持代行

### 2.3 記憶主体 `M`

`M`は経験と現行判断根拠を保持する可変だが受動的な主体である。

必須操作:

```text
ADD REVISE MERGE SPLIT REPLACE INVALIDATE DELETE REINDEX
ROLLBACK ARCHIVE READ QUERY VERSION SNAPSHOT PROVENANCE
```

必須領域:

- active: 現在の判断で引用可能な現行版
- archive: 旧版、生ログ、反証履歴。現行判断へ自動混入しない
- version history: conflict検出とrollback参照

禁止:

- 自律仮説生成
- 自律判断
- 自律mutation開始
- external emit
- 候補採用
- 追記専用への縮退

## 3. `L0`と`P`

### 3.1 Layer-0 `L0`

六つの実行責任を持つ。

1. `SYMBOL_SPACE`
2. `CONTEXT_STATE`
3. `TRANSFORM_OR_WORLD_MODEL`
4. `CANDIDATE_SURFACE`
5. `FITTING_OR_SUCCESS_CRITERION`
6. `EMISSION_INTERFACE`

`L0`は機構であり、task別知識、固定解答、候補順位表を保持しない。

### 3.2 命令形保持体 `P`

`P`は知識、能力、関係、変換規則、パラメータをLayer-0が実行可能な形式で保持する。

必須契約:

```text
validate query digest version provenance serialize load compile
```

必須性質:

- addressable
- state-dependent
- composable
- executable by Layer-0
- deterministic under fixed state
- runtime identity-free
- versioned
- digestable
- provenance-traceable
- Layer-0コードを変更せず交換可能

`P`更新はexplicit compilerだけが行う。runtime経験のHDS承認済み更新先は`M`であり、`P`ではない。

## 4. 外部機構

environment、API、filesystem、network、adapterは主体ではない。

```text
subject = C | J | M
external mechanism = environment | API | storage adapter | transport
```

external mechanismは、HDS承認済みdirectiveを実行して観測結果を返す。判断、計算、保持の固有責任を代行してはならない。

## 5. 権限不変条件

1. J commandなしにC計算を開始しない。
2. PなしにCが仮説・候補を生成しない。
3. C proposalをJ判断なしにactionへ変換しない。
4. J承認なしのM mutationを拒否する。
5. J承認なしのexternal emitを拒否する。
6. directiveは発行実体へ束縛しsingle-useとする。
7. action結果をJが再観測・再評価する前に次の確定writeを行わない。
8. Jはmemoryやenvironmentを直接変更しない。
9. MとPは自律的に計算・判断・放出しない。
10. task/game/level identity、replay、answer map、literal座標、source hidden stateをruntime policyへ渡さない。

## 6. 初期状態と学習compiler

```text
Release State = P0 + J0 + M0 + code + dependency + environment
```

- `P0`: versioned instruction body bundle
- `J0`: 初期purpose、境界、停止・rollback条件
- `M0`: identity-freeなactive/archive初期状態

学習は次の二経路を区別する。

```text
within-run:
  experience -> J authorization -> M revision -> later C/J change

between-version:
  traces + M + ablations + counterexamples
  -> explicit compiler
  -> P^(v+1) / J0^(v+1) / M0^(v+1)
```

単なるログ追記、confidence値だけの変化、未来の計算・判断へ影響しない保存は`G4`を満たさない。

## 7. provenance境界

解析証拠層はsource identityを保持できる。runtimeへ渡すP、M、policyはidentity-freeでなければならない。

```text
analysis evidence:
  source identity allowed for traceability

compiled P / runtime M / runtime policy:
  source identity forbidden
```

holdoutはランダム行分割だけでなく、game family、structure family、action mechanism、layout、color、positionの分離を持つ。

## 8. 最小性命題の有限検査

検査集合:

```text
{}
{C}
{J}
{M}
{C,J}
{C,M}
{J,M}
{C,J,M}
```

期待:

| 構成 | G1 | G2 | G3 | G4 | G5 | 総合 |
|---|---|---|---|---|---|---|
| `{}` | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| `{C}` | PASS | FAIL | FAIL | FAIL | FAIL | FAIL |
| `{J}` | FAIL | PASS | FAIL | FAIL | FAIL | FAIL |
| `{M}` | FAIL | FAIL | PASS | FAIL | FAIL | FAIL |
| `{C,J}` | PASS | PASS | FAIL | FAIL | PARTIAL | FAIL |
| `{C,M}` | PASS | FAIL | PASS | FAIL | FAIL | FAIL |
| `{J,M}` | FAIL | PASS | PASS | FAIL | FAIL | FAIL |
| `{C,J,M}` | PASS | PASS | PASS | PASS | PASS | PASS |

固定pair witness:

- `{C,J}`: `NO_PERSISTENT_EXPERIENCE_CAUSALITY`
- `{C,M}`: `NO_JUDGMENT_OR_AUTHORIZATION`
- `{J,M}`: `NO_GENERATIVE_COMPUTATION`

full setだけがPASSし、proper subsetがすべて固有の観測可能な喪失でFAILした場合だけ、定義域内の機能的最小三構成を主張できる。

## 9. 機能等価物監査

classやfieldを`None`へするだけでは証明にならない。次を検査する。

- 他主体に同じ責任が残っていない
- fallbackが存在しない
- global function、callback、fixtureが代行しない
- fixtureが答えを内包しない
- metadata削除だけでFAILさせていない
- hidden global stateでcycle差やsubject差を捏造していない

## 10. claim規則

claimは次の状態だけを持つ。

- `SUPPORTED`: 実装path、実行test、除去証人が揃う
- `PARTIAL`: 一部機能または統合経路だけが証明済み
- `UNSUPPORTED`: 実装または実行証拠がない
- `REJECTED`: 反証済み、禁止入力、代行、汚染を含む

文書、class名、parameter数、データ件数、単一happy path、scoreだけを`SUPPORTED`の根拠にしない。

## 11. phase順序

```text
P0 Clean Restart Foundation                         complete
P1 Execution Mechanism Foundation                   complete / reclassified
P2 Minimum Three Specification and Root Audit       complete
P3 ARC3 Evidence Material Compiler                  complete
P4 Compute Subject C                                complete
P5 Judgment Subject J                               complete
P6 Memory Subject M                                 complete
P7 Pairwise Subject Audit                           complete
P8 Three-subject Two-cycle Trinity                  complete
P9 Eight-subset Minimum Certificate                 complete
P10 Complete ARC3 Sample Solving                    complete
P11 Release-state Freeze                            complete
P12 Pre-official AGI Conformance and Genericity     complete
P13 Official ARC Connection                         awaiting Owner authorization
P14 Kaggle Paths                                    not started
P15 Submission and Official-result Optimization    not started
```

P12は`ARC3_AGI_ACCEPTANCE_SPEC_REV1.md`の全blocking requirement 57件を
実行証拠で閉じた。P13以降はユーザーの明示的phase開始指示なしに進めない。
