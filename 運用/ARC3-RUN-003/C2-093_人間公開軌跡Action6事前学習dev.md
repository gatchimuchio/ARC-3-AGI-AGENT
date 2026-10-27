# C2-093 人間公開軌跡 Action 6 事前学習 dev

## 目的とデータ境界

公式公開デモの人間操作から、Action 6 の座標特徴ごとの公開応答報酬を集計し、既存の `Action6局所パターン学習` memoryへ初期値として渡す候補を評価した。提出agent・HDS本体・Notebookは変更していない。ゲーム/セッションID、自由記述、固定軌跡、座標値を学習特徴や保存memoryに含めていない。一次情報は[ARC Prizeの人間データ公開記事](https://arcprize.org/blog/arc-agi-3-human-dataset)および[Kaggleの競技データ規則](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/overview/evaluation)。

データはKaggle公開ミラー `magicsword001/arc-agi-3-public-demo-human-testing`。archive SHA-256 `347a4fdba7075babc84b263273122d623fadbe5183b76daa6850534d72039a7c`、157,114,630 bytes、340 recording files、25環境。ARC Prize公式記事は25環境の342 replaysを公開したと記すため、ミラーとの差2件は未解決。Kaggle metadataのlicense表示は `other`。公式記事は公開を明記するが、明示ライセンスは取得できていない。

現在の公開環境metadataとの `game_id` 完全一致をrecording単位で確認し、10環境の163 recordingだけを版適合として残した。残る15環境・177 recordingは版不一致として除外した。train/dev分割は環境単位で、same-environment leakageを避けた。自由記述 `reasoning` は入力特徴に使用していない。

## 評価条件

- code: `検証/ARC3人間公開軌跡Action6事前学習評価.py`。locked local runtime Python 3.12.10、`arc-agi==0.9.8`、`arcengine==0.9.3`。
- human-data split: seed `20261027`、現行版10環境からtrain 7 / dev 3。train群のうち4環境に有効Action 6例があり、3群は有効例なし。Action 6例のある各train環境から544件を均等抽出し、計2,176件をmemoryへ登録。均等化前は21,945件。
- features: clicked-cell color frequency band、same-color 8-neighbor band、edge/interior。候補は応答報酬で初期化し、dev走行中は既存online updateを継続。
- score evaluation: held-out 3 public environments × seeds `7,31,73`、同一環境seed・policy seed、最大80 actions、既存公開RHAE scorer。初期観測は9/9 pair一致。
- 同一候補条件の再実行を1件追加し、Action trace hashとscore/state summaryの一致を確認。

## 結果と採否

| 指標 | 現行policy | 人間prior候補 | 差 |
| --- | ---: | ---: | ---: |
| RHAE平均（9 pair） | 0.000000 | 0.000000 | 0.000000 |
| 改善 / 同点 / 後退 | — | — | 0 / 9 / 0 |
| 完了level差 | — | — | 0 |
| WIN差 | — | — | 0 |
| no-op差 | — | — | 0 |

候補は258回、human-pretrained feature supportのある座標選択を行い、走行中に276件のAction 6応答を追加学習した。行動traceは9組中6組で変化したが、得点・進行・no-op集計には差が出なかった。same-run再実行は一致、illegal action 0、duplicate observation 0。

**候補は不採用。** dev gate `mean ΔRHAE >= +0.01`を満たさず、同条件の実得点が改善しなかった。人間軌跡の読込数やtrace変化を能力向上とは扱わない。公式Notebook/Kernelへの追加、Competition Rerun、提出、quota使用はない。

初回のfull runは、選択されたtrain群の一つに有効Action 6例がなく停止した。代表recordingで観測/行動schemaと272遷移の有効性を確認後、例のないtrain群を0件として扱う修正を入れ、上記の完了runを得た。

## 証拠と再現

- scorecard: `運用/証拠/ARC26-UNIFIED/ARC3-C2-093-human-action6-prior-dev-20261027.json`
- scorecard SHA-256 `034a9d5fcdf5b79cc70a8e0cfb17ad27d3fcb653ed26b04c060acc62a1282cb3`; runner SHA-256 `276a41f62c19e9d46e5d427b3696b1045f7a3a25848be561840217fdfa3ab549`; environment manifest SHA-256 `924f0da0af3bd3b8ac4fa742f35a48f0bf367567f55e8a299588ea710202d97a`; same-candidate trace SHA-256 `348504f09b1cb086240a18dd4527669766fb49a80abc5679d5074c9704fa2357`.
- run command: `& "$env:TEMP\arc3-v6-locked-20261027\Scripts\python.exe" '検証/ARC3人間公開軌跡Action6事前学習評価.py' --human-archive "$env:TEMP\arc-agi-3-public-demo-human-testing.zip" --expected-archive-sha256 347a4fdba7075babc84b263273122d623fadbe5183b76daa6850534d72039a7c --output '運用/証拠/ARC26-UNIFIED/ARC3-C2-093-human-action6-prior-dev-20261027.json'`
- local RHAE only; three held-out environments, no official score claim.
- source constraints: Kaggle competition permits freely/publicly available external data; final evaluation has no internet. The mirror's 340-vs-342 gap and `other` license label remain unresolved, so this mirror was not added to the competition Notebook.
- next direction: use official public observations to train the existing HDS with ID-free pre-state/action/public-outcome examples, then measure prediction quality and game score on environment-held-out groups. Do not promote this Action 6 feature prior.
