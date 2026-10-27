# C6-001 指示書：candidate v4横断回帰・提出物整合監査

- 指示ID: `ARC3-RUN-002-C6-001`
- 版: 1.0／2026-10-23（JST）
- 対象: candidate v4 (`ARC3-SUBMIT-010`) とC2/C3の採用済み公開holdout結果
- 前回基準: C2-003/C3-001/C3-002各運転記録、current remote kernel pull

## 根拠

- v2.0工程表はC6を複数ゲーム・未知状況におけるC1～C5の横断回帰と定義する。
- candidate v4 bundleの提出agent SHAは現行agentと一致する一方、探索policy SHAは現行workspace fileと異なる。
- C2-003は`-1.0` no-op罰を20 holdout環境×seed 7/31/73で受入れ、候補Notebookへ採用した。C3-001/002もGAME_OVER RESET再試行と座標枯渇fallbackを同じholdout条件で受入れた。
- 現行workspace policyには複数ablation用の任意設定が加わっている。差分がcandidateの実行時既定動作を変えないか、未選択ablationがcandidateへ入っていないかを検査する。

## 目的

Kaggleから取得した最新kernel source、local candidate v4 bundle、採用済みC2/C3横断holdout証拠を同一基準で照合する。提出候補に受入済み変更が含まれ、未採用変更が実行動作へ混入していないことを確認する。

## 許可する範囲

- current remote Notebookとmetadata、local `ARC3-SUBMIT-010`、manifestと埋込bundleの読み取り・hash照合。
- candidate policyとworkspace policyのsource差分、agentのpolicy生成引数、既存C2/C3 holdout aggregate/artifactの照合。
- `検証/運転記録/`へ匿名集計と判定を保存する。

## 禁止と保持条件

- runtime/HDS/agent/Notebook/kernelを変更、push、再提出しない。既存quota watcherは稼働維持。
- hidden情報、game/level ID分岐、個別trajectoryを特徴やpolicyへ流入させない。
- local cross-game結果を公式score・hidden performanceとして扱わない。
- `AGENTS.md`、`制御/現在状態.json`、`運用/ARC3文書正本.md`、v2.0正本・v1.0履歴を変更しない。

## 検証

1. 埋込bundle SHA、manifestの35 source全hash、最新remote Notebookの5 cell sourceとlocal candidateの一致を確認する。
2. candidate v4 policy hash `1a89f01a84ed5a3cf3df1e07a9b16c1d74d027960108c82cf5fae5d8dd0b90e5`とworkspace policy差分を列挙し、`MyAgent`が使う既定設定を照合する。
3. bundleがC2-003の固定no-op罰、C3-001/002のRESET/fallback動作を含み、C2/C4等の棄却候補を有効化していないことをコードとC2-003/C3-002 source hash・holdout結果から確認する。
4. C2-003、C3-001/002のholdout結果・違法Action・duplicate・HOLD指標を同じseed条件で照合する。
5. 最新Kaggle履歴にcandidate Rerunがないことを確認し、公式評価の境界を記録する。

## 終了条件

- package/source/default設定の整合性と横断holdout evidenceを示し、C6の採否を決める。
- 不整合があれば、候補v4の公式実行前に原因と修正経路を特定する。
- 合格時はcandidate v4とquota watcherを維持し、クォータ回復後の公式Rerunへ進む。
