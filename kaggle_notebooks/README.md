# kaggle_notebooks/ — Historical rev5.1 Submission Surface

このdirectoryのNotebook／metadata／build reportは、rev5.1 frozen releaseを前提に構築された**履歴提出資産**であり、rev6のCURRENT submissionではない。

現存資産:

- `submission.ipynb`
- `kernel-metadata.json`
- `build-report.json`

`build-report.json`は`arc3-completion-release-rev5-1` datasetと`ARC3CompletionAgent rev5.1 frozen release`を参照する。rev6では当該release claimは完成証拠として失効しているため、このNotebookをそのままcurrent submission経路として扱わない。

削除はしない。Kaggle package構築、依存transport、Notebook実行、platform separationの再監査材料として保存する。

新しいCURRENT Kaggle surfaceはrev6 `M4-P05_KAGGLE_NORMAL_RUN`以降で、同一release artifactに対して再構築する。
