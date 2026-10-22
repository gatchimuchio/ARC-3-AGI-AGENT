# ARC3 Kaggle提出基線

確認日: 2026-10-22。現行作業指示は `運用/ARC3文書正本.md` が指す ARC3 v2.0／`ARC3-RUN-002`。

## 目的と採否

Kaggle Notebookの提出・実行経路を再現可能にし、現行HDSの候補照会と安全な棄権を通す基線を用意する。これは攻略agentではなく、スコア改善を主張しない。

採否: **E0〜E4の既存証拠を再利用し、E5は提出受付済み・採点待ち**。本人のKaggle参加状態は `userHasEntered: true`、Notebook version 5は `COMPLETE`。v2.0指示に基づくCompetition Rerun `57527856` は `PENDING`。公式スコア・完了状態は未取得。E4出力Parquetはplaceholderで、公式得点ではない。

## agentの境界

- `接続/ARC3提出agent.py` は公開観測を既存のARC3境界とHDS候補照会へ渡す。
- `NOT_PLAYED` を初期状態として受けた場合に限り、最初のRESETを一度だけ返す。SDKが初回から `NOT_FINISHED` を示す場合は作用を送らず、候補照会の後にHOLDする。
- 候補やその `実行許可` 自己申告はActionへ昇格しない。盤面や候補本文を永続化しない。
- `制御/現在状態.json`、戦略、HDS、事前記憶は変更せず、提出Notebookにも入力資産・事前記憶・認証情報を入れない。

## Notebookの再生成

生成器はagentとHDS公開packageから静的importで到達するPythonソースだけを決定的に梱包し、各ファイルとbundleのSHA256を記録する。現行bundleは34 source files。`出力/` はGit対象外。

```powershell
python -m uv run --locked python 道具/ARC3提出物構築.py `
  --owner tecchannn `
  --output-dir 出力/ARC3-SUBMIT-NEW
```

Notebook kernel metadataはPrivate、CPU、Internet無効。Kaggleへの保存・実行は生成後に明示的に行う。

```powershell
python -m uv run --locked kaggle kernels push --path 出力/ARC3-SUBMIT-001
python -m uv run --locked kaggle kernels status <owner>/arc3-hds-hold-baseline
python -m uv run --locked kaggle kernels output <owner>/arc3-hds-hold-baseline/<version> `
  --path 出力/ARC3-SUBMIT-001/kaggle-output
```

Save & Run Allではコンペ環境のoffline wheelsでsource importを検査し、placeholder `submission.parquet` を作る。これは採点結果でもCompetition Rerunの受理証拠でもない。実際の競技採点はKernel pageから別途Competition Rerunを開始した場合だけ。

## 検証範囲

- 同一sourceから同一bundle bytes / SHA256を生成。
- 展開後の全source hashとHDS・接続module importを照合。
- Kaggle公式配布RunnerのOFFLINE実環境で、通信なしの0操作HOLDを確認。
- Kaggle Save & Run All version 5がCOMPLETE。出力は `submission.parquet` とlogのみ。Parquetは2,648 bytes、4列・1行のplaceholder、SHA256 `688e716e8f9ad967f6211a3796070b69c74a5adb5ce93e9f1c0ba77701ea3194`。
- source bundleは34 files / 90,859 bytes、SHA256 `0c5ab9f5978617ad5f1e9edf40c165404f563858c6a0c2bf1a00a4827b61f7f1`。version 5 Notebook SHA256 `663ddb0be23d8ced1f8a128e4744ff8582eecb677c3ab7f8d512e84572e4b92a`。

v1.0添付指示書のE5個別承認ゲートは履歴上の旧条件であり、現行v2.0文書により置き換えられた。E5受付・結果の証拠は `検証/運転記録/ARC3-RUN-002_E5-受付_20261022.md` に記録する。Notebook push、Save & Run All、Competition Rerun、公式採点は別段階として記録する。
