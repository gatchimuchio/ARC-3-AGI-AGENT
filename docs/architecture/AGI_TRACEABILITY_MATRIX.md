# AGI最小三構成 Traceability Matrix

- current phase: none (`P12_NOT_STARTED_CURRENT_REQUEST_OUT_OF_SCOPE`)
- last completed phase: `P11_RELEASE_STATE_FREEZE`
- graph: `AGI_OBLIGATION_GRAPH.json`
- status vocabulary: `SUPPORTED | PARTIAL | UNSUPPORTED | REJECTED`

`実装済み`は実行pathと試験が存在することだけを意味する。後続phaseの完成を意味しない。

## Matrix

| 要素 | 定義・必要性 | 入力 → 出力 | 状態所有者・更新者 | 権限 | 実装path・呼出経路 | 単体試験・除去証人 | 代行可能性 | 未実装・過剰主張 |
|---|---|---|---|---|---|---|---|---|
| `L0` | Pを参照・変換・候補化・放出する機構。Cの実行面に必要 | Observation/Context/P material → typed proposals/authorized effects | Contextは`CONTEXT_STATE`、機構codeはruntime中不変 | 採否不可。承認済みwrite/emitの実行のみ | `roles.py`, `kernel.py::Layer0Kernel` | 六責任除去とP4の8対象除去監査 | PやJが変換機構を代行してはならない | P4範囲で`SUPPORTED` |
| `P` | 知識・能力・関係・規則・parameterの命令形保持体。`C=Execute(L0,P)`に必要 | request/Observation/Context/M view → rules, predictions, priors, uncertainty | P bundleが所有。explicit compilerだけが更新 | 採否・write・emit不可 | `s5_policy.py`, `s5_compute.py`, `bundles/s5_rendered_policy_v1.*` | schema/tamper/identity、Teacher-forced error 0、S5 183/183、byte rerun | Teacher graph/training corpusをRuntime Pへ戻さない | S5 Runtime PとP0 release束縛は`SUPPORTED` |
| `C` | L0とPの結合で成立する計算主体。G1の唯一owner | J compute request + Observation + P + optional M view → hypotheses/counter-hypotheses/predictions/candidates/update/output proposals | 一時的compute stateはC。P/Mは別owner | proposalのみ。最終判断不可 | `kernel.py::PureLLMCompute`, `roles.py` | `test_compute_subject_p4.py`; C removal固有witness | Jが仮説生成、Mがcandidate生成してはならない | standalone G1は`SUPPORTED`; 後続G4/sample汎化は未主張 |
| `J` | HDS Frameを閉包し採否・停止・許可を決めるG2 owner | purpose/X/R/Mc/evidence/risk/budget → decision/authorization judgment | Jがdecision stateを所有・更新 | command、accept/reject、REOBSERVE/SUSPEND/STOP/rollback、write/emit許可 | `judgment.py`, `judgment_fixtures.py`, `kernel.py::HDSController` | 676 Frame、全status、negative、J removal、integrated binding、S5 rollback/reset | Cがdecisionを作る、Mが許可する経路は禁止 | standalone/integrated OFFLINE境界で`SUPPORTED` |
| `M` | 経験・現行根拠を改訂可能に保持するG3 owner | explicit/authorized operation + expected version + payload → new snapshot/version | Mがactive/archive/version/history/provenanceを所有。runtime mutationはCがJ指令下で実行 | 自律mutation・判断・計算不可 | `memory.py::PassiveMemory`, `memory_fixtures.py` | 全15操作、stale、rollback、archive、query、687 fixture、M removal | Pをruntime Mとして更新、Jがstorageを持つことは禁止 | standalone G3は`SUPPORTED`; G4は未主張 |
| environment boundary | 主体外の観測・作用機構 | authorized action → rendered result | environmentが外部stateを所有 | 判断不可。HDS directiveなしstep不可 | `adapters/offline_arcade.py`, `s5_runtime.py` | non-OFFLINE拒否、HDS reset/emit/result、S5 183/183 | direct `environment.step` fallback禁止 | P11 releaseはOFFLINE限定で`SUPPORTED`; official接続は未評価 |
| learning compiler | 解析/trace/Mからidentity-free P0/J0/M0を明示生成 | provenance-bearing evidence → normalized fixtures/versioned bundles | compilerがartifactを所有。runtimeは読取のみ | runtime自律実行不可。provenance manifestはruntime使用禁止 | `s5_training_corpus.py`, `s5_policy_compiler.py`, `p11_release.py` | corpus/policy決定性、error 0、P0/J0/M0 descriptor、release manifest | raw logやruntime callbackをcompiler代行にしない | P11 release範囲で`SUPPORTED` |
| `P0` | 起動時の命令形保持体初期版 | compiled bundle → runtime P | P bundle | explicit version adoptionのみ | `bundles/s5_rendered_policy_v1.*`, `p11_release.py` | policy digest、parameter、identity、initial descriptor、release digest | code内seedをP0と呼ばない | P11 release manifestへ束縛済みで`SUPPORTED` |
| `J0` | 起動時purpose/boundary/stopping/rollback条件 | release bundle → initial HDS state | J | Jだけがdecisionを更新 | `HDSFramePolicy`, `HDSController`, `p11_release.py` | policy digest、全initial authority count 0、release digest | config labelだけでJ0としない | P11 release manifestへ束縛済みで`SUPPORTED` |
| `M0` | identity-free active/archive初期状態 | release bundle → initial memory snapshot | M | HDS承認済みmutationだけ | `PassiveMemory`, `p11_release.py` | version 0、active/archive 0、snapshot/release digest | raw analysis identity混入禁止 | P11 release manifestへ束縛済みで`SUPPORTED` |
| external emission | HDS承認済みactionの機械的実行 | owner-bound single-use directive → signed result | environment stateは外部、receiptはdirective | HDS許可必須 | `in_memory.py`, `offline_arcade.py`, `kernel.py::execute_emission` | copy/replay/tamper/forged label拒否 | C/Jからのdirect step禁止 | P1範囲で`SUPPORTED` |
| memory write | HDS承認済みmutationの機械的実行 | bound directive + payload + expected version → mutation result | M | HDS許可必須、Cが実行 | `memory.py::apply_authorized` | payload/target/version/single-use/observation gate | J direct write、M self-write禁止 | authority adapterは`SUPPORTED`; pair/Trinity接続はP7/P8 |
| HDS Frame | purpose/X/R/Mc/evidence/risk/unknownsを閉じる判断入力 | supplied fixture/proposal → deterministic decision | J | G2全権限 | `judgment.py::HDSFrame`, integrated Frame adapter | 676 fixture、missing X/R/Mc、hazard、budget、contradiction、rollback | Jは入力candidateを選ぶだけで生成しない | P5範囲で`SUPPORTED` |
| cycle transition | command→compute→judge→act→observe→write→rejudge | cycle t state → cycle t+1 state | C/J/Mが各固有stateを所有 | stageごとのauthority invariant | `kernel.py`, `trinity.py`, `sample_runtime.py` | two full cycles、M citation、P/J/M isolation | hidden global stateで差を作らない | P8範囲でG4/G5 `SUPPORTED` |
| stopping | 未閉包、hazard、budget、WINで停止/保留する | Frame/result → REOBSERVE/SUSPEND/STOP/REJECT | J | Jのみ | `HDSJudgmentSubject`, `judge_emission_result` | hazard priority、terminal、budget、missing closure | environmentやCのsilent stopを判断扱いしない | `SUPPORTED` |
| rollback | Jが条件を判定しM/実行状態を指定版へ戻す | contradiction/failure/version ref → rollback decision/result | Jが許可、Mが版を保持、Cが実行 | Jのみ許可 | `judgment.py`, `memory.py::ROLLBACK`, `s5_authority.py` | J condition/reference、M指定版復元、S5 GAME_OVER/reset回復 | exception retryをrollbackと呼ばない | standalone/integrated S5で`SUPPORTED` |
| minimum-three certificate | G1〜G5に対するC/J/M構成最小性を有限実行証明する | 8 subset実行証拠 → certificate/witness/graph/report | certificate builderが決定論的artifactを所有 | claim昇格のみ。runtime権限なし | `certificate.py`, `certificates/p9/` | 8 subset、3 removal、leak 0、byte rebuild | metadata削除やfixture answerでFAILを捏造しない | 定義済みG1〜G5範囲で`SUPPORTED`; sample攻略・汎化は非主張 |

## Current call graph

```text
OFFLINE rendered frame
  -> SYMBOL_SPACE
  -> CONTEXT_STATE
  -> HDSController.issue_compute
  -> PureLLMCompute
       -> InstructionBody.query
       -> P-provided hypothesis / prediction / control material
       -> world-model / candidate mechanisms
  -> success criterion
  -> HDSController.judge
  -> authorized emission
  -> rendered result
  -> HDS result judgment
  -> authorized version-bound memory mutation
  -> next observation / judgment
```

P11固定edge:

```text
P10 evidence + compiled Runtime P
  -> P0/J0/M0 descriptors
  -> full regression + reproducible package
  -> P11 release manifest
     arc3_p11_release_state:
     70ffdd4395d0f50b312c002b226bd8c92ec1818597e913a72310dd1739177848
```

## P3以降の確定順序

1. P3で全解析素材をaccountingし、identity-free fixtureへ変換する。
2. P4でP-A/P-BとC単独を実装する。
3. P5でstandalone Jを実装する。
4. P6でfull mutable Mを実装する。（完了）
5. P7で三pairを固有witnessによりFAILさせる。
6. P8で二周期因果と主体別因果分離を証明する。
7. P9で全8部分集合を有限列挙する。
8. P10で初めて全sample攻略を開始する。
9. P11でrelease stateを固定する。（完了）

## P7 pairwise disposition

`pairwise.py`は三つのproper pairを実行し、各pairの成立責任を観測した後だけ
固定witnessを返す。結果は`{C,J}=G3/G4 FAIL`、`{C,M}=G2 FAIL`、
`{J,M}=G1 FAIL`で、witness重複0、functional-equivalent leak 0である。
詳細証拠は`P7_PAIRWISE_SUBJECT_AUDIT.md`を正本とする。

## P8 Trinity disposition

`trinity.py`は二つのfull authority cycleとP/J/M一因子比較を実行する。
cycle 2はcycle 1 post-write Mのversion/digestを明示引用し、M-onlyでC prediction、
P-onlyでC output、J-onlyでJ decision/authorizationだけが変化する。
同一input replay一致、hidden-global delta 0、authority violation 0である。
詳細証拠は`P8_TRINITY_TWO_CYCLE_CAUSALITY.md`を正本とする。

## P9 minimum-three disposition

`certificate.py`は空集合、single 3件、pair 3件、full Trinityの全8 subsetを
固定順序で実行する。proper subset 7件は各責任を実行後に固定witnessでFAILし、
full setだけがG1〜G5をPASSする。欠落主体fieldと欠落主体固有出力を二重監査し、
functional-equivalent leakは0件である。5 artifactはdigest付きで
`certificates/p9/`へ固定し、再生成byte一致を試験する。詳細証拠は
`P9_MINIMUM_THREE_CERTIFICATE.md`を正本とする。
