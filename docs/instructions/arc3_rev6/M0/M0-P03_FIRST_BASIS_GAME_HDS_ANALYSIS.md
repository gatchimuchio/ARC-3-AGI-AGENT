# M0-P03 — 最初のBasis Game深層HDS解析

- Point ID: `M0-P03_FIRST_BASIS_GAME_HDS_ANALYSIS`
- Depends on: M0-P02 PASS
- Next: `M0-P04_FIRST_BASIS_GAME_CAPABILITY_IMPLEMENTATION`

## 目的

first basis gameの全levelを、製品へ実装可能なMechanism Segmentへ分解する。

## 分解階層

```text
Game → Level → Phase → Mechanism Segment → Action Macro → raw step span
```

## HDS必須項目

```text
Purpose Tree
W=(X,R,Mc)
entity／role／relation
state variables
action semantics
precondition
immediate／delayed effect
goal／hazard
order／loop／phase
subgoal
probe／rollback
counter-hypotheses
Failure Signature
Applicability Predicate
```

## 必須作業

1. terminalから成功要因を逆算する。
2. baseline、alternative、counter-hypothesisを作る。
3. progress／failure／phase change／delay地点でフルHDSを行う。
4. 同型反復をMacroへ圧縮する。
5. 全raw actionをsegmentへ所属させる。
6. 各segmentにproduct mapping候補を付ける。

## 出力

`analysis/product/rev6/basis/<game>/task_mechanism_record.json`

## Hard Exit

```text
all levels covered
all raw actions assigned once
all segments have purpose/precondition/operation/effect/termination
counter-hypotheses present at mechanism decisions
product mapping candidate present
unresolved terms explicit
```

## 禁止

- action列のruntime格納
- 全一手への重複文書
- mappingのないanalysis completion
- 他basis game解析の同時開始

## Failure Routing

open termで実装責任が決まらない場合はM0-P03内で追加観測し、推測でM0-P04へ送らない。
