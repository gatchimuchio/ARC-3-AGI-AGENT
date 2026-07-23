# P6 記憶主体M 実装・完了証拠

- phase: `P6_MEMORY_SUBJECT_M`
- state: `COMPLETE`
- predecessor: `P5_JUDGMENT_SUBJECT_J`
- successor: `P7_PAIRWISE_SUBJECT_AUDIT`
- runtime scope: identity-free standalone storage / HDS-authorized OFFLINE adapter
- official / competition connection: prohibited
- HDS judgment: `PASS`

## 1. Work-block FrameSpec

```text
X:
  P3 memory_lifecycles 687 records
  existing provisional PassiveMemory
  existing owner-bound HDS MemoryDirective

R:
  explicit low-level operation
    -> validate identity/provenance/version/precondition
    -> mutate or read the M-owned state
    -> record snapshot/provenance
  HDS-authorized runtime directive
    -> verify capability/owner/payload/version
    -> execute the same mutation semantics

Mc:
  M owns active/archive/version/history/provenance
  M creates no hypothesis/candidate/decision/authorization
  M starts no autonomous mutation and performs no external emit
  stale expected version -> fail without state change
  rollback -> copy the specified historical state into a new monotonic version
  M removal -> fixed functional-loss witness

non-goals:
  pair/Trinity/subset proof, two-cycle G4, sample solving, release freeze
```

## 2. Storage subject

`arc3_agi_agent.memory.PassiveMemory`は次の15操作を明示APIで実装する。

| 区分 | 操作 |
|---|---|
| mutation | `ADD`, `REVISE`, `MERGE`, `SPLIT`, `REPLACE`, `INVALIDATE`, `DELETE`, `REINDEX`, `ROLLBACK`, `ARCHIVE` |
| read | `READ`, `QUERY`, `VERSION`, `SNAPSHOT`, `PROVENANCE` |

mutationはcompare-and-swapの`expected_version`、evidence signature、
provenanceを必須とする。各成功mutationはversionを1だけ進め、active/archiveを
含むsnapshotとprovenance eventを保存する。`ROLLBACK`はversion番号を巻き戻さず、
指定snapshotの内容を新しいversionへ復元する。

active entryとarchive entryは別store・別順序で保持する。容量超過時も削除せず
archiveへ移す。queryは現在version、query条件、active/archive順序に対して
決定的である。

保持payloadは次を失わず格納できる。

```text
current purpose, current state, hypothesis, support, contradiction,
failure, evidence, lifecycle, unresolved item, provenance,
version, rollback reference
```

## 3. 二つの実行境界

### storage単体API

`execute_storage(MemoryOperation)`はC/Jを必要としないテスト・storage境界である。
呼出し自体は明示的であり、Mが自律的に開始する処理はない。

### runtime authority adapter

`apply_authorized(...)`は次をすべて検証してから、同じstorage意味論を実行する。

- HDS decision validity
- owner-bound single-use capability
- decision/directive binding
- payload digest binding
- pure-LLM executor
- runtime identity-free payload
- expected/current version一致

stale versionを含む拒否ではdirectiveをconsumeせず、M stateも変更しない。

## 4. Fail-closedと除去証人

非canonical/cyclic payload、task/game/level identity、source path、
不正split/merge、存在しない対象、stale versionは明示例外となる。

Mのsourceには`HypothesisIR`、`CandidateIR`、`HDSJudgmentSubject`、
external emission実行面がなく、G1/G2を代行しない。

standalone harnessとintegrated kernelの両方で、M除去は次の固定証人となる。

```text
MEMORY_SUBJECT_REMOVED_NO_G3_VERSIONED_EXPERIENCE_RETENTION
```

## 5. P3 fixture適合

全687 memory lifecycle fixtureをtyped recordへ変換し、全recordで
compare-and-swap、archive policy、identity-free flagを検証した。

mutation candidate coverage:

```text
ADD          678
REVISE       504
MERGE        678
SPLIT        136
REPLACE      677
INVALIDATE   136
DELETE         1
REINDEX      677
ROLLBACK     677
ARCHIVE      504
```

この件数はstorage契約の実証素材coverageであり、sample攻略性能を意味しない。

## 6. 検証

- P6 dedicated tests: 8 PASS
- compileall: PASS
- full unit suite: 166 PASS
- strict mypy: 23 source PASS
- ruff: PASS
- integration: 2 PASS
- 25 sample OFFLINE 1-action regression: 25/25 execution、error 0

全unit、integration、OFFLINE regressionを連結した最初のcommandは全体timeout
120秒に到達したが、その時点でunit 166とintegration 2はPASS済みだった。
OFFLINE regressionは単独再実行しexit 0を確認した。これは環境実行時間による
検証harness timeoutであり、product regressionではない。

P6はG3 standaloneだけを`SUPPORTED`とする。周期間G4、pair、Trinity、
全8 subset、全sample level攻略、汎化、release固定は未成立。次phaseはP7。
