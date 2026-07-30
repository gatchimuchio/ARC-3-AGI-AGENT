# ARC3 rev3 Strategy Rebaseline

- strategy: `HDS_DISTILLATION_FIRST`
- active phase: `PH-D00A`
- base commit: `1eece1f21926be24c7c13608eb81f1d0a3f76614`
- base tree: `d63d26e25758211938cc33d0efe84f50ed096023`
- Codex role: `DEVELOPMENT_META_C`
- Owner / Meta-J: 大平鉄兵
- state: `IN_PROGRESS`

## Active selector

```text
PH-R00 [OWNER_APPROVED_PASS]
→ PH-D00A [ACTIVE]
→ PH-D00B ... PH-D14
→ PH-B00 ... PH-B06
→ PH-A00 ... PH-A08
→ PH-E00 ... PH-E04
```

`PH-D04`はARC2専用であり、ARC3 Trackでは実行しない。

## Hard gates

```text
HDS_STRUCTURE_BUNDLE_OWNER_APPROVED
```

以前にTrack Bへ進まない。

```text
DISTILLED_INITIAL_STATE_BUNDLE_FROZEN
```

以前にTrack Aへ進まない。

## Current asset decision

- P16〜P21は`PRESERVE_INFRASTRUCTURE_CANDIDATE`。
- P16〜P21の旧`PASS`はcurrent commit/treeへbindされておらず、rev3のOwner承認済みphase証拠ではない。
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

## Authority state

提供済み6文書はbyte-preservingで配置し、digestを
[`REV3_AUTHORITY_INPUT_MANIFEST.json`](REV3_AUTHORITY_INPUT_MANIFEST.json)
へ固定した。

HDS蒸留仕様、HDS蒸留roadmap、HDS内部／外向け正本、
Self-Contained Promptは全てbyte-preservingで保持し、記載SHA-256との一致を確認した。
required authority不足は0である。

PH-R00のcommit bind、自己監査、Owner Reviewは閉じられ、
`control/rev3/OWNER_APPROVAL_RECORDS/PH-R00.json`にOwner決定を固定した。
同Recordの連続進行許可により、通常phaseはphase固有の証拠境界を保ったまま進める。
Rule採否、構造bundle採択、locked final、official、Kaggleは個別Owner決定を要する。

## Claims

現時点で許可する表現:

```text
REV3_AUTHORITY_RETAINED
PH_R00_OWNER_APPROVED_PASS
PH_D00A_IN_PROGRESS
HISTORICAL_POLICY_QUARANTINED
ACTIVE_RUNTIME_CAPABILITY_NOT_ESTABLISHED
```

禁止する表現:

```text
HDS_DISTILLATION_COMPLETE
GENERIC
AGI
OFFICIAL_READY
```
