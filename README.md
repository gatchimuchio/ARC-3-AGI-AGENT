# ARC3公式サンプル汎用完遂AGI

本repositoryの当該開発endpointは、公式ARC3サンプル25 game／183 levelを同一のC／J／M／P構造で自律完遂する`ARC3CompletionAgent`です。

## Current Authority

- [仕様書 rev6](docs/strategy/ARC3公式サンプル汎用完遂AGI_実装仕様書_rev6.md)
- [ロードマップ rev6](docs/roadmap/ARC3公式サンプル汎用完遂AGI_開発ロードマップ_rev6.md)
- [Point別指示書 Index](docs/instructions/arc3_rev6/INDEX.md)
- [Current Selector](control/CURRENT_SELECTOR.json)

## Current Status

```text
Product status: NOT_ESTABLISHED
Current Point: R0-P01_INVALIDATE_REV5_1_FALSE_CLOSURE
Auto advance: false
```

rev5.1は公式public score 0.06を得たにもかかわらず`PRODUCT_RELEASED`を宣言したため、製品完成証拠として失効しました。旧artifactは履歴として保存します。

## rev6の物理構造

```text
仕様書 1 file
ロードマップ 1 file
共通実行契約 1 file
Point別指示書 33 files
機械可読Roadmap Manifest
Current Task / Current Selector
```

各Pointは独立ファイルです。一冊の巨大指示書から複数工程を機械的に通過させません。

## Product Formula

```text
C = Execute(L0, P)
AGI Kernel = Trinity(C, J_hds, M)
```

進捗はgame WIN、level complete、Failure Signature減少、P/J/M能力差分だけで測定します。
