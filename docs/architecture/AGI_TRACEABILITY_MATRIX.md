# AGI最小三構成 Traceability Matrix

- current phase: `P8_THREE_SUBJECT_TWO_CYCLE_TRINITY`
- last completed phase: `P7_PAIRWISE_SUBJECT_AUDIT`
- graph: `AGI_OBLIGATION_GRAPH.json`
- status vocabulary: `SUPPORTED | PARTIAL | UNSUPPORTED | REJECTED`

`実装済み`は実行pathと試験が存在することだけを意味する。後続phaseの完成を意味しない。

## Matrix

| 要素 | 定義・必要性 | 入力 → 出力 | 状態所有者・更新者 | 権限 | 実装path・呼出経路 | 単体試験・除去証人 | 代行可能性 | 未実装・過剰主張 |
|---|---|---|---|---|---|---|---|---|
| `L0` | Pを参照・変換・候補化・放出する機構。Cの実行面に必要 | Observation/Context/P material → typed proposals/authorized effects | Contextは`CONTEXT_STATE`、機構codeはruntime中不変 | 採否不可。承認済みwrite/emitの実行のみ | `roles.py`, `kernel.py::Layer0Kernel` | 六責任除去とP4の8対象除去監査 | PやJが変換機構を代行してはならない | P4範囲で`SUPPORTED` |
| `P` | 知識・能力・関係・規則・parameterの命令形保持体。`C=Execute(L0,P)`に必要 | request/Observation/Context/M view → rules, predictions, priors, uncertainty | P bundleが所有。explicit compilerだけが更新 | 採否・write・emit不可 | `instruction_body.py`, `instruction_compiler.py`, `bundles/` | schema/tamper/identity、P-A/P-B swap、byte rebuild、P removal | `roles.py`に固定規則fallbackなし | P-A/P-Bとcompilerは`SUPPORTED`; P0 release固定はP11 |
| `C` | L0とPの結合で成立する計算主体。G1の唯一owner | J compute request + Observation + P + optional M view → hypotheses/counter-hypotheses/predictions/candidates/update/output proposals | 一時的compute stateはC。P/Mは別owner | proposalのみ。最終判断不可 | `kernel.py::PureLLMCompute`, `roles.py` | `test_compute_subject_p4.py`; C removal固有witness | Jが仮説生成、Mがcandidate生成してはならない | standalone G1は`SUPPORTED`; 後続G4/sample汎化は未主張 |
| `J` | HDS Frameを閉包し採否・停止・許可を決めるG2 owner | purpose/X/R/Mc/evidence/risk/budget → decision/authorization judgment | Jがdecision stateを所有・更新 | command、accept/reject、REOBSERVE/SUSPEND/STOP/rollback、write/emit許可 | `judgment.py`, `judgment_fixtures.py`, `kernel.py::HDSController` | 676 Frame、全status、negative、J removal、integrated binding | Cがdecisionを作る、Mが許可する経路は禁止 | standalone G2は`SUPPORTED`; integrated rollback接続はP8 |
| `M` | 経験・現行根拠を改訂可能に保持するG3 owner | explicit/authorized operation + expected version + payload → new snapshot/version | Mがactive/archive/version/history/provenanceを所有。runtime mutationはCがJ指令下で実行 | 自律mutation・判断・計算不可 | `memory.py::PassiveMemory`, `memory_fixtures.py` | 全15操作、stale、rollback、archive、query、687 fixture、M removal | Pをruntime Mとして更新、Jがstorageを持つことは禁止 | standalone G3は`SUPPORTED`; G4は未主張 |
| environment boundary | 主体外の観測・作用機構 | authorized action → rendered result | environmentが外部stateを所有 | 判断不可。HDS directiveなしstep不可 | `adapters/offline_arcade.py`, `sample_runtime.py` | integration no-network、forged directive、non-OFFLINE拒否 | direct `environment.step` fallback禁止 | P10までOFFLINE限定。現経路は`SUPPORTED` |
| learning compiler | 解析/trace/Mからidentity-free P0/J0/M0を明示生成 | provenance-bearing evidence → normalized fixtures/versioned bundles | compilerがartifactを所有。runtimeは読取のみ | runtime自律実行不可。provenance manifestはruntime使用禁止 | `evidence_compiler.py`, `instruction_compiler.py` → datasets/manifests/P bundles | P3 12-file/P4 3-file byte rebuild | raw logやruntime callbackをcompiler代行にしない | P bundle形成済み。J0/M0/release P0はP5/P6/P11 |
| `P0` | 起動時の命令形保持体初期版 | compiled bundle → runtime P | P bundle | explicit version adoptionのみ | なし | P11でdigest rebuild試験 | code内seedをP0と呼ばない | `UNSUPPORTED` |
| `J0` | 起動時purpose/boundary/stopping/rollback条件 | release bundle → initial HDS state | J | Jだけがdecisionを更新 | なし | P11でrebuild試験 | config labelだけでJ0としない | `UNSUPPORTED` |
| `M0` | identity-free active/archive初期状態 | release bundle → initial memory snapshot | M | HDS承認済みmutationだけ | なし | P11でsnapshot/digest試験 | raw analysis identity混入禁止 | `UNSUPPORTED` |
| external emission | HDS承認済みactionの機械的実行 | owner-bound single-use directive → signed result | environment stateは外部、receiptはdirective | HDS許可必須 | `in_memory.py`, `offline_arcade.py`, `kernel.py::execute_emission` | copy/replay/tamper/forged label拒否 | C/Jからのdirect step禁止 | P1範囲で`SUPPORTED` |
| memory write | HDS承認済みmutationの機械的実行 | bound directive + payload + expected version → mutation result | M | HDS許可必須、Cが実行 | `memory.py::apply_authorized` | payload/target/version/single-use/observation gate | J direct write、M self-write禁止 | authority adapterは`SUPPORTED`; pair/Trinity接続はP7/P8 |
| HDS Frame | purpose/X/R/Mc/evidence/risk/unknownsを閉じる判断入力 | supplied fixture/proposal → deterministic decision | J | G2全権限 | `judgment.py::HDSFrame`, integrated Frame adapter | 676 fixture、missing X/R/Mc、hazard、budget、contradiction、rollback | Jは入力candidateを選ぶだけで生成しない | P5範囲で`SUPPORTED` |
| cycle transition | command→compute→judge→act→observe→write→rejudge | cycle t state → cycle t+1 state | C/J/Mが各固有stateを所有 | stageごとのauthority invariant | `kernel.py`, `sample_runtime.py` | one-action re-observation、next judgment input | hidden global stateで差を作らない | M-only因果未証明で`PARTIAL` |
| stopping | 未閉包、hazard、budget、WINで停止/保留する | Frame/result → REOBSERVE/SUSPEND/STOP/REJECT | J | Jのみ | `HDSJudgmentSubject`, `judge_emission_result` | hazard priority、terminal、budget、missing closure | environmentやCのsilent stopを判断扱いしない | `SUPPORTED` |
| rollback | Jが条件を判定しM/実行状態を指定版へ戻す | contradiction/failure/version ref → rollback decision/result | Jが許可、Mが版を保持、Cが実行 | Jのみ許可 | `judgment.py`, `memory.py::ROLLBACK` | J condition/reference、M指定版復元試験 | exception retryをrollbackと呼ばない | JとMの単体は実装済み、integrated接続はP8で`PARTIAL` |

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

欠落している必須edge:

```text
M revision -> later C/J behavioral delta
identity-free P3 fixtures -> J/M implementation -> P0/J0/M0
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
9. P11でrelease stateを固定する。

## P7 pairwise disposition

`pairwise.py`は三つのproper pairを実行し、各pairの成立責任を観測した後だけ
固定witnessを返す。結果は`{C,J}=G3/G4 FAIL`、`{C,M}=G2 FAIL`、
`{J,M}=G1 FAIL`で、witness重複0、functional-equivalent leak 0である。
詳細証拠は`P7_PAIRWISE_SUBJECT_AUDIT.md`を正本とする。
