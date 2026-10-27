# ARC3-RUN-003 C2-042：現行agent提出候補bundle再生成

## 目的・根拠

- 正本：`ARC3-RUN-003` v3.0（2026-10-24）。
- 現行agent `接続/ARC3提出agent.py` のSHA256は `47539cd3c0a19b033fb782df61e4275062b8f7b2343eca3376fbda9b50237486`、source bundleは `d00ab4af0613a4949e13a886fbaf12a5b61c868c3aaaac42320ba38d1268301e`。
- 保存済み `出力/ARC3-SUBMIT-010` はbundle `974029af7f66b774c96af3cf86b2344905bf68a0c83445fd366c74dd779e54d9`、agent `c334797618dcb154b32f0797adac6a18fa3752a715d28f5f520c95c14cbbdc95` で、現行sourceではない。
- 現行bundleと一致するOFFLINE official Starter 25環境実行は既存証拠 `P1-3_officialStarter_public25-20261024T111429Z.json` にあり、2000 SDK steps、4 level進行、0 wins、illegal 0。提出適格性や公式scoreの証拠ではない。

## 許可範囲

- 変更先は新規 `出力/ARC3-SUBMIT-011/` のみ。既存候補、source、証拠を上書きしない。
- 現行bundleからprivate Kaggle Notebook、kernel metadata、bundle manifestを再生成し、含有source・SHAを検証する。
- `検証/test_ARC3提出物構築.py` を実行し、既存OFFLINE Starter 25環境証拠とbundle SHAを照合する。
- AGENTS.md、`制御/現在状態.json`、source、HDS、Notebook v5、既存Kaggle kernel、提出履歴、提出枠は変更しない。git stage/commit/reset/pushなし。
- Kaggle kernel push、Save & Run All、Competition Rerun、提出は本タスクの範囲外。直近公式観測は提出枠0（2026-10-24T10:48:04Z）であり、現行枠を推定しない。

## 受入条件

1. 生成先が新規で、生成Notebook・metadata・manifestが同じbundleに対応する。
2. bundle SHAが現行 `接続/ARC3提出agent.py` のmanifestと一致し、既存OFFLINE Starter 25環境実行のbundle SHA `d00ab4af0613a4949e13a886fbaf12a5b61c868c3aaaac42320ba38d1268301e` と一致する。
3. Notebookはprivate、Internet/GPU無効、対象competition sourceのみを指定し、hidden answerや事前記憶を含めない。
4. builder targeted testsがPASSし、source再現・公式score・攻略能力の主張を混同しない。
5. 証拠と採否をappend-only work ledgerへ追記し、protected-file hashとdirty diff保持を確認する。

## 採否・次の作業

一致と試験PASSなら「現行agentのローカル提出候補bundle再現済み」として保管する。公式提出適格性は未成立のままにする。次の公式操作前にKaggle履歴・rules/timeline・UTC日付・実測quota・Notebook保存実行・SHAを再確認する。
