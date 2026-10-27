# C2-022 公開初期観測hash seedの開発ablation

## 目的

C6-003では環境seedを固定してもpolicy seedだけで公開holdoutの完了levelが1〜4に変動した。既定seedを保持せず、探索開始時の公開観測から一般的・決定的なpolicy RNG seedを得る評価専用ablationを開発splitで試す。

seed materialは最初の`NOT_FINISHED`観測の`状態`、`最新盤面`、昇順の`作用可能番号`をcanonical JSON（UTF-8、sort keys、compact separators）へ変換し、SHA-256 digest先頭8 byteをunsigned big-endian整数として使う。game/level ID、画像filename、既知trajectory、hidden情報は使わない。

## 保持条件と範囲

- `接続/観測駆動探索Action.py`、提出agent、HDS、Notebook/kernel、保護ファイルは変更しない。ablationとCLI flagは`検証/ARC3探索Actionローカル評価.py`内だけ。
- 初回`NOT_FINISHED`より前は現在のpolicy seedで初期化する。初回探索Actionを選ぶ直前に一度だけ観測hashで`_rng`を置き換え、RESET・GAME_OVER・level間は同一run内のrng stateを保持する。
- split seed `20261022`、dev 5公開環境、environment seeds 7/31/73、最大80 Action、GAME_OVER後RESETを維持。
- baselineは同じ環境seedの現行policy、candidateは観測hash seed。開始盤面・合法Action・Action予算を対にして比較する。

## 事前採否条件

devで次を全て満たす場合だけ未使用holdoutへ進める。

1. 3 seed全てでcompleted levelsがbaseline以上、少なくとも2 seedでlevelを失わない。
2. 総no-opが減り、少なくとも2/3 seedで悪化しない。GAME_OVER増加が合計1件を超えない。
3. 同一公開開始観測を同一条件で再実行した時、hash seedと各探索Action結果が完全一致する。
4. illegal Action、duplicate step、policy HOLDはbaselineから増えない。

条件を満たさない場合はruntime候補・holdoutへ進めず、結果を保存して次課題へ移る。C6-003で見つかったseed29の高成績を固定値として流用しない。

## 検証と記録

- CLI flag `--hash-seed-from-initial-observation`でbaseline/candidateを比較できるようにする。
- canonical seed導出と一度だけ適用する挙動をtargeted testsで検証し、既存flagとのablation同時指定は拒否する。
- artifactは`出力/ARC3-RUN-002-local/C2-022-hashseed-dev-seed-<seed>.json`と未使用summaryへ保存し、個別ID・board・座標を記録レポートへ転載しない。
- report: `検証/運転記録/ARC3-RUN-002_C2-022_公開初期観測hashseed開発ablation_20261023.md`。
