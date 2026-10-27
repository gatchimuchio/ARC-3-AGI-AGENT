# ARC3-RUN-003 C2-063：level進行の遅延credit paired ablation

## 結果

- 固定dev split 5公開環境×seeds `7/31/73`、最大80手、全15対。
- previous/candidate開始条件15/15一致。最初のlevel進行まで（進行がないrunは全区間）のAction/応答prefixは15/15一致。scorecard契約違反、illegal action、duplicateは0。
- 平均RHAEは両条件`0.240596656`、平均差`0.0`。改善0・後退0・同点15。完了levelは両条件3、WIN0、no-op差0。GAME_OVER差は合計`-1`。

candidateはlevel進行時、直前最大4手へ合計2.0の公開進行creditを幾何重みで配分したが、スコアもlevel数も増えなかった。

**判定：C2-063棄却。** holdout、共有policy/runtime採用、Notebook/kernel変更へ進まない。

## 再現・境界

- 固定条件：[C2-063](../../運用/ARC3-RUN-003/C2-063_level-progress遅延信用ローカルablation.md)
- Runner SHA-256 `71aad00f3771b5efeacc30045fda49f78025aac1838542d878cfa4543b16d79b`
- policy SHA-256 `a86af8296bf5438c92b1249f9643bc12bf546227a60f0633cc2dc3805b0b1bc8`
- Ruff整形後に同一条件で再実行。匿名scorecard `運用/証拠/ARC26-UNIFIED/P1-3_delayed-level-credit-dev_20261027_r2.json`、SHA-256 `f1288d2f0550b7b3e2b88953d6e4bc4f06729193a8a6b9194d1ff7d7324fe9a3`。
- 探索policy単体の公開offline評価。HDS、official submission、Kaggle quotaは未使用。
