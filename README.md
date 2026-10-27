# ARC-3 Agent

> 2026-10-27の研究成果保存版です。正本はARC26 v6。ソース・検証結果・負の結果・未採用候補を含む保存範囲と復元手順は [成果保存案内](運用/GitHub成果保存/20261027/README.md)、最新の実測値は [現行実力基準線](運用/ARC3-RUN-003/C1-023_v6現行実力基準線.md) を参照してください。未採用候補の性能向上やmainへの採用を示す版ではありません。

ARC Prize 2026 / ARC-3を対象に、学習機械・事前記憶・公式入力・評価環境を用いて汎用agentを開発・検証するrepository。

## 現行基底

- 学習機械: `HDS/学習系統/v0.4.2`
- 事前記憶: `記憶/事前記憶/v0.4`
- 公式入力: `入力/`
- 現在状態: `制御/現在状態.json`

## 開発環境

Python 3.12.10 / uv 0.12.19で依存を固定している。
Windowsでの復元、公式環境25個の取得、オフライン動作確認、試験手順は
[接続/開発環境.md](接続/開発環境.md) を参照する。

```powershell
$env:PYTHONUTF8 = '1'
python -m uv sync --locked
python -m uv run --locked python 道具/開発環境確認.py --offline-game
```

初回は手順書に従ってKaggle配布物を取得する。認証情報・配布本体・実行生成物はGit管理対象外。

Kaggle Notebookの提出基線、保存・実行とCompetition Rerunの区別は
[接続/ARC3提出.md](接続/ARC3提出.md) を参照する。

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
