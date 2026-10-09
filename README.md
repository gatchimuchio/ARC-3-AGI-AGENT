# ARC-3 Agent

ARC Prize 2026 / ARC-3を対象に、学習機械・事前記憶・公式入力・評価環境を用いて汎用agentを開発・検証するrepository。

## 現行基底

- 学習機械: `HDS/学習系統/v0.4.2`
- 事前記憶: `記憶/事前記憶/v0.4`
- 公式入力: `入力/`
- 現在状態: `制御/現在状態.json`

## Repository Map

```text
AGENTS.md             AI作業者の運用契約
制御/                 現在状態
運用/                 権限・日本語基底・repository運用
HDS/                  学習機械基底
記憶/                 事前記憶・実行時記憶
入力/                 ARC3公式入力資産
接続/                 ARC・Kaggle・環境等の外部境界
戦略/                 ARC3攻略戦略
検証/                 実行結果と証拠
道具/                 repository監査工具
```

旧構成・過去の実装候補はGit履歴に残るが、現在の権威ではない。Ownerの明示指示なしに復活させない。

```bash
python3 道具/リポジトリ環境監査.py
```
