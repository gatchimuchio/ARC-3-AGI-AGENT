# ARC3 rev3 Strategy Rebaseline

- strategy: `HDS_DISTILLATION_FIRST`
- active phase: `PH-R00`
- work block: `WB-PH-R00-CURRENT-HEAD-REBIND-20260731`
- source commit: `4dbb65c5d45cca3402f326b251c1de6ac4a2e554`
- source tree: `44ccb73437480daeaab71e6cb3119b5e6bc5d485`
- Codex role: `DEVELOPMENT_META_C`
- Owner / Meta-J: 大平鉄兵
- phase state: `IN_PROGRESS`

## Active selector

```text
PH-R-1 [OWNER_APPROVED_PASS]
→ PH-R00 [ACTIVE / CURRENT_HEAD_REBIND]
→ PH-D00A ... PH-D14
→ PH-B00 ... PH-B06
→ PH-A00 ... PH-A08
→ PH-E00 ... PH-E04
```

`PH-D04`はARC2専用であり、ARC3 Trackでは実行しない。

## Entry binding

PH-R00 entryは次へexact bindされている。

```text
PH-R-1 Evidence Commit
= 3fec094d64d599681a5bb7c10ebda8163747dc10

PH-R-1 Evidence Payload
= sha256:1f03eb8c4ba134803ccb82323fa1cefef59706066f854c64c4f21717b32051a4

PH-R-1 → PH-R00 ApprovalRecord
= owner-approval-record:fcfc55bcd7e1aa8b28101870cab844679014a6338cb5a7899a379e0241f290c9

PH-R00 WorkBlockFrame
= rev3-work-block-frame:ac14d98087e931677f48c68d2e8f47c83dcb642ff51d13a24c85a59678fb92bb
```

このentryはPH-R00だけを許可する。HDS蒸留、Bridge、AGI Runtime、
locked final、official、Kaggleを許可しない。

## Current asset decision

- P16〜P21は`PRESERVE_INFRASTRUCTURE_CANDIDATE`。
- P16〜P21の旧`PASS`はlegacy evidenceであり、rev3の能力完成claimではない。
- PH-R00はcurrent source commit/tree上で、基盤候補の存在、回帰、package surface、
  import boundaryを再検証する。
- S5、compiled policy、P22、CVは`HISTORICAL_QUARANTINE`。
- historical assetをrev3 production parent、active policy、fallbackへ使用しない。
- rev3 active runtime countは0。能力claimは`NOT_ESTABLISHED`。

機械可読な分類は
[`ASSET_CLASSIFICATION_REV3.json`](ASSET_CLASSIFICATION_REV3.json)
を正本とする。

## Production selection

`arc3_agi_agent.rev3_governance`は、将来のrev3 production選択を
`DISTILLED_INITIAL_STATE_BUNDLE`に限定する。

以下をfail closedで拒否する。

- S5 runtime / S5 compiled policy
- known-sample Student
- P22 compiled policy / CV artifact
- rev1 runtime
- teacher trajectory
- fallbackを一件でも持つselection
- Owner approval digestを含まないselection

このguardはAGI能力実装ではない。PH-R00のproduction selection境界である。

## Evidence model

PH-R00は次の非自己参照構造で閉じる。

```text
Source Commit / Tree
→ Implementation Commit / Tree
→ Evidence Commit / Payload Digest
→ EvidenceCommitAttestation
→ standing authorizationの条件評価
→ PH-R00 result ApprovalRecord / PH-D00A entry
```

PH-R00の完了証拠には、full unit、integration、local package build、
archive inspection、local notebook build／validation／runtime smoke、
production import audit、artifact determinismを含める。

## Hard gates

```text
HDS_STRUCTURE_BUNDLE_OWNER_APPROVED
```

以前にTrack Bへ進まない。

```text
DISTILLED_INITIAL_STATE_BUNDLE_FROZEN
```

以前にTrack Aへ進まない。

## Claims

現時点で許可する表現:

```text
REV3_STRATEGY_OWNER_APPROVED
PH_R1_OWNER_APPROVED_PASS
PH_R00_ENTRY_AUTHORIZED
PH_R00_IN_PROGRESS
P16_P21_INFRASTRUCTURE_CANDIDATE
HISTORICAL_POLICY_QUARANTINED
ACTIVE_RUNTIME_CAPABILITY_NOT_ESTABLISHED
```

PH-R00 evidenceが閉じる前に禁止する表現:

```text
PH_R00_OWNER_APPROVED_PASS
DEPENDENCY_LOCK_PASS
HDS_DISTILLATION_COMPLETE
GENERIC
AGI
OFFICIAL_READY
```
