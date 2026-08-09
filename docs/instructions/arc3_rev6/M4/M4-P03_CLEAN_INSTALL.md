# M4-P03 — Clean Install

- Point ID: `M4-P03_CLEAN_INSTALL`
- Depends on: M4-P02 PASS
- Next: `M4-P04_CLEAN_FULL_SAMPLE_RERUN`

## 目的

release artifactが開発tree、cache、secret、外部未固定assetなしにfresh environmentで起動することを確認する。

## 必須作業

1. fresh environmentを作る。
2. release artifactだけをinstallする。
3. dependency解決を確認する。
4. ProductBundleをloadする。
5. C／J／M／P self-checkを実行する。
6. official adapterの初期観測と合法action変換をsmokeする。
7. development pathへのimportを監査する。

## Hard Exit

```text
clean_install = PASS
external_development_tree_access_count = 0
secret_finding_count = 0
release_bundle_load = PASS
C_J_M_P_self_check = PASS
official_adapter_smoke = PASS
runtime_identity_matches_freeze = true
```

## 禁止

- 開発repositoryをPYTHONPATHへ追加
- missing assetを手動copy
- teacher corpus mount
- clean install後のcode patch

## Failure Routing

package／dependency問題はM4-P02へ戻す。能力問題はM3以前へ戻す。
