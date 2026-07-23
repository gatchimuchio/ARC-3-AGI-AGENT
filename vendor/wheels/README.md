# Vendor wheels

このディレクトリは、旧ルート直下に置かれていた31個のPython wheelを集約した
非権威のベンダー保管領域です。

- 依存関係の正本: `ARC-AGI-3-Agents/pyproject.toml`
- 再現用lockの正本: `ARC-AGI-3-Agents/uv.lock`
- solverの設計・判断・runtime routing入力としては使用しない
- wheelの更新・削除時は、取得元、対応platform、hash、lock整合を同時に監査する

再配置ではファイル名とGit blob IDを維持し、binary内容を変更しません。
