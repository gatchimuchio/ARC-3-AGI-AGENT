# M4-P01 — Release Bundle Compilation

- Point ID: `M4-P01_RELEASE_BUNDLE_COMPILATION`
- Depends on: M3-P06 PASS
- Next: `M4-P02_CODE_DEPENDENCY_RESOURCE_FREEZE`

## 目的

M3を通過したACTIVE_DEV能力だけを、一つのRELEASE_FROZEN P／J0／M0へ再コンパイルする。

## 入力許可

```text
ACTIVE_DEV capabilities
M3 conformance evidence
M2 full-sample evidence
fixed type/operator registry
```

## 入力禁止

```text
LOCAL_M
PROBATION_DEV
rejected/rolled-back capability
unresolved open term
identity/replay contaminated asset
live human decision
complete action sequence
```

## 必須作業

1. release対象能力を列挙する。
2. P／J0／M0責任へ再配置する。
3. provenanceとApplicabilityを固定する。
4. one ProductBundleを構築する。
5. development-only source／teacher artifactがpackageに入らないことを確認する。
6. release bundleをloadしてself-checkする。

## Hard Exit

```text
release_bundle_count = 1
asset_stage = RELEASE_FROZEN
included_PROBATION_count = 0
included_LOCAL_M_count = 0
identity_replay_finding_count = 0
complete_action_sequence_count = 0
bundle_load_self_check = PASS
```

## 禁止

- M4で新能力を発明
- current Runtime Mの丸ごとM0化
- rev5.1 release bundleの親利用

## Failure Routing

能力不足が判明した場合はM1／M2／M3へ戻り、M4内で修正しない。
