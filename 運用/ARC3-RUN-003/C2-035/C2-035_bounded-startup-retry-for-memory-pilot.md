# ARC3-RUN-003 C2-035：memory pilotのためのbounded起動再検査

## 目的と根拠

C2-034のversion 9はoffline benchmark前に失敗した。固定1080秒のreadiness deadline時点で`serve.log`はmodel shard 38件中28件の読み込みを記録し、推論readyは未確認だった。memory条件・ゲーム行動は一切観測されていない。version 8では904秒でreadyに達した記録があるため、不完全shardの直接証拠に基づいて、有限の起動期限で一度だけ再検査する。期限を無制限に延ばさない。

## 検証仮説

private kernelの共通server起動readiness上限を1080秒から1800秒へ延ばせば、固定modelのloadが完了しoffline benchmarkを開始できる。1800秒以内にreadyとbenchmark開始の双方が確認できなければ、今回得られた証拠の範囲でこのmodel経路を止め、さらに期限を延ばさない。

## 実行計画

- C2-034のoff/slim Notebookコピーを入力にする。model、prompt、server args、sampling、`LOCAL_ANALYZER_SEED=0`、offline対象3ゲーム、160 Action/game、1200秒/game、1 pass、逐次実行、private GPU、Internet無効を保持する。
- C2-034からの共通動作変更は`SERVER_STARTUP_TIMEOUT=1800`秒のみ。controlは`ARC3_MEMORY_SECTIONS=off`、treatmentは`slim`。arm間の唯一のsolver差はmemory mode。
- version 10 controlをouter timeout 10800秒で先に一度だけpushする。`/health_generate` ready、offline benchmark開始、3件すべての初期状態証拠を確認できた場合に限り、結果を保存してからversion 11 treatmentを一度だけpushする。
- game IDは開始状態と出力の対応照合だけに使い、policyへ渡さない。`記憶/事前記憶/v0.4`、trajectory、answer map、private/hidden評価情報を読み込まない。
- Kaggle Competition Rerun、公式提出、公式採点を行わない。

## 採否条件

最初にreadyとbenchmark時刻を確認する。両armが完了し、3件すべての初期board/state/levelが一致した場合だけ、levels、WIN、Actions、no-op、GAME_OVER、経過時間、generated tokens、timeout、および`slim` memory更新の後続prompt再注入を比較する。集計level deltaが正、WIN件数が非減、更新・再注入・開始一致が実証されれば、次taskで独立seed再現を行う。3ゲーム1 seedの結果でruntime採用、公式候補昇格、公式score改善は主張しない。

どちらかのarmがreadiness期限に達した場合はpaired comparison不成立として閉じ、startup期限をさらに延ばさず、v3の公開HDS/runtime作業へ戻る。
