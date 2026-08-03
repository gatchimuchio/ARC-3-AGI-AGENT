# M4-P02 — Code／Dependency／Resource Freeze

- Point ID: `M4-P02_CODE_DEPENDENCY_RESOURCE_FREEZE`
- Depends on: M4-P01 PASS
- Next: `M4-P03_CLEAN_INSTALL`

## 目的

release ProductBundleを実行するcode、dependency、resource、adapter、entrypointを一意に固定する。

## 必須作業

1. source commit／treeを固定する。
2. dependency versionを固定する。
3. action／time／memory budgetを固定する。
4. official adapter configを固定する。
5. one entrypointを固定する。
6. package allowlistを固定する。
7. reproducible buildを二回行いbyte一致を確認する。

## Hard Exit

```text
source_identity_fixed = true
dependency_pin_mismatch_count = 0
entrypoint_count = 1
release_bundle_count = 1
reproducible_build_count >= 2
byte_mismatch_count = 0
capability_change_count = 0
```

## 禁止

- freeze中の能力変更
- fallback P／bundleの同梱
- development corpus／source treeの同梱
- 複数entrypoint

## Failure Routing

能力変更が必要ならM4を中断し、原因Pointへ戻る。package問題だけを本Pointで修正する。
