# ARC3-RUN-003 C2-062：現行探索horizon 80/160手の公開RHAE対比較

## 結果

- 固定dev split 5公開環境×policy/environment seeds `7/31/73`、最大80手と160手、全15対を完了。
- previous/candidateの初期公開条件は15/15一致。80手までのAction引数・公開応答prefixも15/15一致。scorecard契約違反、illegal action、重複観測は0。
- 平均RHAEは80手`0.240596656`、160手`0.240596656`、差`0.0`。改善0・後退0・同点15。完了levelは両条件3、WINは両条件0。
- candidateはAction総数`1,200→2,400`、no-op`35→84`（+49）、GAME_OVER`18→52`（+34）、RESET`18→48`（+30）。追加80手で進行しなかった。

**判定：C2-062棄却。** dev gateの平均score改善を満たさないためholdoutへ進まない。160手設定をruntime/Notebookへ反映しない。

## 再現・境界

- 条件と採否gate：[C2-062](../../運用/ARC3-RUN-003/C2-062_MyAgent探索horizonローカルscorecard.md)
- Runner SHA-256 `f9b1c43fd3453348bce2fa2bcc805c0691c4b51d192059c1d44ad29441ee160f`
- policy SHA-256 `a86af8296bf5438c92b1249f9643bc12bf546227a60f0633cc2dc3805b0b1bc8`
- Public environment metadata manifest SHA-256 `320cc4f2fc697d5bc39131ebce0c0188b2d12fccbb6ba7364ccac394bea728f6`
- Ruff整形後に同一条件で再実行。匿名scorecard `運用/証拠/ARC26-UNIFIED/P1-3_action-horizon-dev_20261027_r2.json`、SHA-256 `bf2e06294b3c656a8b0d819ea5bfff40e273534cb2627c0d8ce5463b8c4c7a37`。
- 評価は探索policy単体（HDS query/updateなし）。HDS guidanceの独立paired試験では15対中guided action 0件。HDS runtime、公式score、Notebook/kernelは変更・評価していない。
