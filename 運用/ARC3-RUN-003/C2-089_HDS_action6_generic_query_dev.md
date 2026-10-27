# C2-089 HDS Action 6 generic query dev

## 問いと変更範囲

本作業単位の開始時に、現行v6.0共通3点セットとARC3専用3点セットの全6文書を確認した。

現行agentはAction 6の座標引数をHDS照会へ渡さず、HDS action-ranking queryからもAction 6を除外している。公開25環境から固定したdev 5開始点・seed 7/31/73で、既存HDS応答記憶を「Action 6、引数あり」の一般カテゴリとして照会するだけで、予測と攻略得点が変わるか調べた。

変更は検証専用variantに隔離した。候補が有効な非座標Actionを返した場合は現行の優先を保ち、他候補がない場合だけAction 6をHDSへ追加照会する。HDSが順位候補を返した場合も座標選択は現行の合法探索policyが行う。Notebook・提出agent・HDS本体は変更していない。ゲームID、level ID、正解、固定操作列は使用しない。

## 固定条件と再現

- 実行環境：`%TEMP%/arc3-v6-locked-20261027/Scripts/python.exe`、Python 3.12.10、`arc-agi==0.9.8`、`arcengine==0.9.3`。
- HDS：`HDS/学習系統/v0.4.2`。同じSDK環境・公開25 metadata manifest・split seed `20261022`を使用。
- 比較：current agent対検証variant、5公開dev開始点×seed 7/31/73、1エピソード最大80 action。各pairは同じSDK seed・公開開始metadataを使った。初期観測hashは保存していないため、開始盤面のhash一致までは主張しない。
- 再実行時の1 pair終了ごとに集計行をJSONLへ同期保存した。最初の実行では全15 pairの計算終了後、最終JSON保存が`OSError: [Errno 28] No space left on device`で失敗し、出力は0 byteだった。数値を回収できなかったため、同条件で最初から再実行した。下記の採否はcheckpoint付き再実行だけに基づく。

## 結果

| 指標 | current agent | Action 6 query variant | 差 |
|---|---:|---:|---:|
| public dev RHAE mean（15 pair） | 0.240596656 | 0.240596656 | 0.000000000 |
| 改善 / 同点 / 後退 | — | 0 / 15 / 0 | — |
| 完了level差 | — | — | 0 |
| WIN差 | — | — | 0 |
| no-op差 | — | — | 0 |
| HDS Action 6予測候補 | — | 0 | — |
| HDSで誘導されたAction 6 | — | 0 | — |

seed別の両条件meanはseed 7=`0.238095238`、seed 31=`0.146987366`、seed 73=`0.336707364`で同一だった。Action 6 queryを15 pairで試したが、HDSは一度も予測候補を返さず、走行軌跡・スコアも変化しなかった。dev gate（平均差+0.01以上）不通過のため**不採用**。これはlocal public RHAEであり、Kaggle公式scoreではない。

## 証拠と制約

- 実験器：`検証/ARC3HDSAction6候補照会ablation.py` SHA-256 `ebac124777ed506ec9ab22a732060c175b5cb382613787fe38fadafeb281765b`
- 集計JSON：`運用/証拠/ARC26-UNIFIED/P1-3_HDS_action6_generic_query_dev_20261027.json` SHA-256 `ce9d426e97f3f1eb0034e0db293c313e944c286ad2c15739b0bf4866907b82a5`
- ペア別checkpoint：`運用/証拠/ARC26-UNIFIED/P1-3_HDS_action6_generic_query_dev_20261027.jsonl` SHA-256 `18b5996e9d613958d41fcf4b0d2be12ffa337fb0e2e20f74c68b7be31a511cb0`
- HDSは候補を返さなかったが、その内部の具体的な棄却理由はこのscorecardで採録していない。したがって「座標文脈不足が原因」とまでは確定していない。次はquery状態/有効原理/条件一致件数を公開入力から集約し、action-level一般化が成立しない理由を特定する。
- Kaggleは2026-10-27 05:43 UTCにread-onlyで再照会。submission `57688735`は`PENDING`でpublic/private score空欄。C2-087 AとC2-088 version 1は`QUEUED`、C2-087 Bはstatus query 404でremote kernelなし。quota viewのraw表示は`timeUsed=83940.699.0s`, `totalTimeAllowed=21600s`, `timeReserved=0s`, refresh `2026-10-31T00:00:00Z`。以前の観測に記録されたtotal allowance 108000sと異なるため意味を推測せず、再開前に再照会する。今回、push・Notebook変更・Competition Rerun・submissionは実施していない。
