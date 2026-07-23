# AGI最小三構成 Traceability Matrix

- phase: `P2_AGI_MINIMUM_THREE_AUDIT`
- graph: `AGI_OBLIGATION_GRAPH.json`
- status vocabulary: `SUPPORTED | PARTIAL | UNSUPPORTED | REJECTED`

`実装済み`は実行pathと試験が存在することだけを意味する。後続phaseの完成を意味しない。

## Matrix

| 要素 | 定義・必要性 | 入力 → 出力 | 状態所有者・更新者 | 権限 | 実装path・呼出経路 | 単体試験・除去証人 | 代行可能性 | 未実装・過剰主張 |
|---|---|---|---|---|---|---|---|---|
| `L0` | Pを参照・変換・候補化・放出する機構。Cの実行面に必要 | Observation/Context/P material → typed proposals/authorized effects | Contextは`CONTEXT_STATE`、機構codeはruntime中不変 | 採否不可。承認済みwrite/emitの実行のみ | `roles.py`, `kernel.py::Layer0Kernel` | `test_each_single_role_removal_has_unique_functional_loss`; 六固有witness | PやJが変換機構を代行してはならない | 六責任は実装済みだがPを実行していないため`PARTIAL` |
| `P` | 知識・能力・関係・規則・parameterの命令形保持体。`C=Execute(L0,P)`に必要 | request/Observation/Context/M view → rules, predictions, priors, uncertainty | P bundleが所有。explicit compilerだけが更新 | 採否・write・emit不可 | 現行実装なし | 固定予定: `INSTRUCTION_BODY_REMOVED_NO_EXECUTABLE_KNOWLEDGE_OR_TRANSFORM` | `roles.py`の固定規則を機能等価物として残してはならない | `UNSUPPORTED`; P1をC完成と呼ばない |
| `C` | L0とPの結合で成立する計算主体。G1の唯一owner | J compute request + Observation + P + optional M view → hypotheses/counter-hypotheses/predictions/candidates/update/output proposals | 一時的compute stateはC。P/Mは別owner | proposalのみ。最終判断不可 | `kernel.py::PureLLMCompute`は暫定実装 | `test_full_set_establishes_one_authorized_cycle`は機構証拠のみ | Jが仮説生成、Mがcandidate生成してはならない | P不在、反対仮説・prediction IR不足のため`UNSUPPORTED` |
| `J` | HDS Frameを閉包し採否・停止・許可を決めるG2 owner | purpose/X/R/Mc/evidence/risk/budget → decision/directives | Jがdecision stateを所有・更新 | command、accept/reject、SUSPEND/STOP/rollback、write/emit許可 | `kernel.py::HDSController`; integrated cycleから呼出 | command/decision/directive攻撃試験、hazard veto、STOP試験 | Cがdecisionを作る、Mが許可する経路は禁止 | integrated authorityは`PARTIAL`; C/Mなしのstandalone Frame API未実装 |
| `M` | 経験・現行根拠を改訂可能に保持するG3 owner | authorized operation + expected version + payload → new snapshot/version | Mがactive/archive/versionを所有。mutationはCがJ指令下で実行 | 自律mutation・判断・計算不可 | `memory.py::PassiveMemory` | unauthorized write拒否、single-use payload binding | Pをruntime Mとして更新、Jがstorageを持つことは禁止 | ADD/DELETE相当のみ。全操作、conflict、rollback、archive、query未実装で`PARTIAL` |
| environment boundary | 主体外の観測・作用機構 | authorized action → rendered result | environmentが外部stateを所有 | 判断不可。HDS directiveなしstep不可 | `adapters/offline_arcade.py`, `sample_runtime.py` | integration no-network、forged directive、non-OFFLINE拒否 | direct `environment.step` fallback禁止 | P10までOFFLINE限定。現経路は`SUPPORTED` |
| learning compiler | 解析/trace/Mからidentity-free P0/J0/M0を明示生成 | provenance-bearing evidence → versioned bundles | compiler outputが各初期状態を所有 | runtime自律実行不可。HDS採択対象 | 現行実装なし | P3でmanifest/reproducibility/identity-free/holdout試験 | raw logやruntime callbackをcompiler代行にしない | `UNSUPPORTED` |
| `P0` | 起動時の命令形保持体初期版 | compiled bundle → runtime P | P bundle | explicit version adoptionのみ | なし | P11でdigest rebuild試験 | code内seedをP0と呼ばない | `UNSUPPORTED` |
| `J0` | 起動時purpose/boundary/stopping/rollback条件 | release bundle → initial HDS state | J | Jだけがdecisionを更新 | なし | P11でrebuild試験 | config labelだけでJ0としない | `UNSUPPORTED` |
| `M0` | identity-free active/archive初期状態 | release bundle → initial memory snapshot | M | HDS承認済みmutationだけ | なし | P11でsnapshot/digest試験 | raw analysis identity混入禁止 | `UNSUPPORTED` |
| external emission | HDS承認済みactionの機械的実行 | owner-bound single-use directive → signed result | environment stateは外部、receiptはdirective | HDS許可必須 | `in_memory.py`, `offline_arcade.py`, `kernel.py::execute_emission` | copy/replay/tamper/forged label拒否 | C/Jからのdirect step禁止 | P1範囲で`SUPPORTED` |
| memory write | HDS承認済みmutationの機械的実行 | bound directive + payload → mutation result | M | HDS許可必須、Cが実行 | `memory.py::apply_authorized` | payload/target/single-use/observation gate | J direct write、M self-write禁止 | operation意味論不足で`PARTIAL` |
| HDS Frame | purpose/X/R/Mc/evidence/risk/unknownsを閉じる判断入力 | fixture/proposal → deterministic decision | J | G2全権限 | ClosureIRとHDSControllerに分散 | missing X/R/Mc、hazard、budget試験の一部あり | candidate fixtureが答えを内包しないこと | standalone typed Frame未実装で`PARTIAL` |
| cycle transition | command→compute→judge→act→observe→write→rejudge | cycle t state → cycle t+1 state | C/J/Mが各固有stateを所有 | stageごとのauthority invariant | `kernel.py`, `sample_runtime.py` | one-action re-observation、next judgment input | hidden global stateで差を作らない | M-only因果未証明で`PARTIAL` |
| stopping | 未閉包、hazard、budget、WINで停止/保留する | Frame/result → SUSPEND/STOP/REJECT | J | Jのみ | `HDSController.judge`, `judge_emission_result` | hazard priority、terminal WIN、budget test | environmentやCのsilent stopを判断扱いしない | rollbackを除く停止は`SUPPORTED` |
| rollback | Jが条件を判定しM/実行状態を指定版へ戻す | contradiction/failure/version ref → rollback directive/result | Jが許可、Mが版を保持、Cが実行 | Jのみ許可 | protocol labelのみ | なし | exception retryをrollbackと呼ばない | operation未実装で`UNSUPPORTED` |

## Current call graph

```text
OFFLINE rendered frame
  -> SYMBOL_SPACE
  -> CONTEXT_STATE
  -> HDSController.issue_compute
  -> PureLLMCompute
       -> roles.py embedded world-model rules
       -> roles.py embedded candidate metrics
  -> success criterion
  -> HDSController.judge
  -> authorized emission
  -> rendered result
  -> HDS result judgment
  -> authorized ADD-like memory mutation
  -> next observation / judgment
```

欠落している必須edge:

```text
PureLLMCompute -> InstructionBody.query
M revision -> later C/J behavioral delta
J rollback authorization -> M rollback execution
analysis evidence -> identity-free compiler -> P0/J0/M0
```

## P3以降の確定順序

1. P3で全解析素材をaccountingし、identity-free fixtureへ変換する。
2. P4でP-A/P-BとC単独を実装する。
3. P5でstandalone Jを実装する。
4. P6でfull mutable Mを実装する。
5. P7で三pairを固有witnessによりFAILさせる。
6. P8で二周期因果と主体別因果分離を証明する。
7. P9で全8部分集合を有限列挙する。
8. P10で初めて全sample攻略を開始する。
9. P11でrelease stateを固定する。
