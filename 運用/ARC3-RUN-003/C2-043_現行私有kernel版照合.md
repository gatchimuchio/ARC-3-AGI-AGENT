# ARC3-RUN-003 C2-043：現行私有kernel版照合

## 目的

公式Notebook version 5の23.86は現行ローカルagentに帰属しない。現行agent候補は `出力/ARC3-SUBMIT-011/` に生成済みで、builder tests 5件PASS、source bundle SHA256 `d00ab4af0613a4949e13a886fbaf12a5b61c868c3aaaac42320ba38d1268301e`、Notebook SHA256 `bb34b2a0b6d04e84d2a27cacb44db623233d2e367a800b2ab59e0a0383ca8e80`。

同じkernel slug `tecchannn/arc3-observation-driven-exploration-candidate` はKaggle上に存在し `COMPLETE` と返る。remote current versionをread-onlyでpullし、ローカル候補との版差を特定する。旧versionやprivate sourceは上書きしない。

## 許可範囲

- Kaggle CLI `kernels pull` によるread-only取得とローカル新規監査ディレクトリへの保存。
- Notebook/metadataのSHA256、source bundle digest、version metadata有無のみ照合する。secret値、問題答え、evaluation情報は表示・保存しない。
- Kaggleへのkernel push、Save & Run All、Competition Rerun、提出、quota消費はしない。
- 保護ファイル、agent/HDS/runtime、既存候補・Notebook・運転記録を上書きしない。

## 受入条件

1. Remote pullは成功し、保存先は新規である。
2. remote notebook/metadata digestとlocal `SUBMIT-011` digestを記録し、版の一致/不一致を明示する。
3. 取得物の秘匿監査は値を出力せず結果だけ保存する。
4. 公式提出・score・runtime成功の主張をしない。結果と次の公式操作ゲートを追記型台帳へ保存する。
