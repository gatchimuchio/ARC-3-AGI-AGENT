# ARC-3 Agent

ARC Prize 2026 / ARC-3を対象に、HDS・記憶・公式入力・外部接続を用いて汎用agentを開発・検証するrepository。

## 現行基底

- HDS: `HDS/`
- 学習機械: `HDS/学習系統/v0.4.2`
- 事前記憶: `記憶/事前記憶/v0.4`
- 現在状態: `制御/現在状態.json`

## Repository Map

```text
AGENTS.md             AI作業者の運用契約
制御/                 現在状態
運用/                 権限・日本語基底・repository運用
HDS/                  観測・判断・学習
記憶/                 Prior / Runtime Memory
入力/                 ARC3公式入力の受け口
接続/                 外部Adapter境界
戦略/                 ARC3攻略戦略
検証/                 成立確認・回帰・証拠
道具/                 repository監査
```

旧rev・旧戦略・旧実装はGit履歴に残るが、Ownerの明示指示なしに現行権威へ戻さない。
