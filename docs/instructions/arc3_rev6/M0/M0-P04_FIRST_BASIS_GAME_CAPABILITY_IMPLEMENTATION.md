# M0-P04 — 最初のBasis Game製品能力実装

- Point ID: `M0-P04_FIRST_BASIS_GAME_CAPABILITY_IMPLEMENTATION`
- Depends on: M0-P03 PASS
- Next: `M0-P05_FIRST_ONLINE_TRINITY_WIN`
- Product code change: 必須

## 目的

TaskMechanismRecordを、既存product pathが実行するP／J／M能力へ変換する。

## 実装先

```text
Runtime M / LOCAL_M
P_dev / PROBATION_DEV
J_dev domain judgement
M_dev retrieval/update
C representation/hypothesis/planning
既存Adapter（観測損失が実証された場合のみ）
```

## 必須作業

1. 現行P／P-IRの不足operatorを実装する。
2. Cがmechanism／counter-mechanism／planを生成できるようにする。
3. Jがexecute／probe／wait／rollback／resetを採否できるようにする。
4. Mがsupport／refute／invalidate／replaceできるようにする。
5. capabilityをactual runtimeへloadする。
6. capability使用traceを取得する。

## 必須能力候補

first gameに必要なものだけを実装する。例:

- multi-layer representation
- goal/mechanism induction
- action-effect prediction
- ACTION6 binding
- subgoal／bounded plan
- temporal attribution

## Hard Exit

```text
product runtime loads capability
C cites capability in output
J accepts/rejects capability-derived candidate
M can revise/invalidate capability-local model
no new parallel agent path
no fixed trajectory table
no game-ID selector
```

## 禁止

- shell／runner作成
- reportだけで終了
- RELEASE_FROZENへの直接昇格
- teacher packageのruntime import

## Failure Routing

runtimeが能力を使用しない場合はimplementation incomplete。M0-P05へ進まない。
