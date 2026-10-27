# ARC3-RUN-003 C2-034 実行記録（追記専用）

## 2026-10-24 JST：準備・control開始

- 正本: v3.0／`ARC3-RUN-003`。基底Git SHAは`8667e9b9512e328084050007d3bdedb1ae5e245f`、branch `main`。既存dirty worktreeは保持し、stage/commit/resetなし。
- Kaggle正しいcompetition slug `arc-prize-2026-arc-agi-3` を2026-10-23 22:43 UTC頃にread-only照会。最新`57541830 COMPLETE / public 0.25 / private blank`、前版`57527856 COMPLETE / public 0.00 / private blank`。履歴に新規提出なし。ARC2共通wrapperは`arc-prize-2026-arc-agi-2`へ接続するためARC3証拠には使わず、正確なARC3 slugを指定したKaggle CLI出力だけを採用した。
- Notebook v8 base SHA-256 `449b57c9eca8f24a6338b5eb6f68d231a2fab4185073293a79c00581f85a5a05`。
- control Notebook SHA-256 `6aec28df091fd15401e023a515b2d5deb11479c7cd5126d5f4246ef845d92a42`。treatment Notebook SHA-256 `966b715da3046d22db7edf04f4637c28768a9d8bc4eda811af91a14b646fbc0a`。両者はnbformat validate PASS。Notebook cell 5以外のsolver codeは同一で、cell5差分は`ARC3_MEMORY_SECTIONS=off`対`slim`だけ。両armはseed `0`、offline game limit `3`、160 Action、1,200秒/game、1 pass、逐次、private GPU、Internet無効。元Notebookとkernel metadataは不変更。
- `tecchannn/arc3-model-guided-c2-025`のversion 8 status `COMPLETE`を確認後、version 9 controlを2026-10-23 22:39:30–22:43:45 UTCの間にpush。直後read-only statusは`RUNNING`。private ordinary kernel runのみで、Competition Rerun／公式提出は実施していない。
- C:空き容量は`1,249,062,912` bytes。出力取得は必要な要約・transcript/logを優先し、既存大容量requests/states pickleを無条件に再取得しない。

## 継続状態

control version 9完了後に必要artifactを取得・検査し、その後treatment version 10を一度だけpushする。各armの開始board/state/level一致、memory write/reinjection、per-game結果を確かめてからdeltaと採否を追記する。private実験中につきC2-034未完了。

## 2026-10-24 JST：version 9 control結果

- Kernel version 9 statusは`ERROR`。kernel logは`DEADLINE after 1080s from server launch; server inference readiness was not confirmed`を記録し、offline benchmark未開始。`benchmark.json`、`summary.txt`、`prompt.log`、episode eventは出力に見当たらず、levels/Actions/WINは未観測。
- `serve.log`最後のweight progressは`74% / 28 of 38 shards / 17:00 elapsed`。readiness前にモデルweightロードが終わらなかったことは直接観測した。`wrapt` import警告とtransformers rope警告もあるが、単独原因とは判定しない。
- 取得ログSHA-256: `serve.log`=`DE8ACD5FD76DA5B9E54D54D6B83A07622244D6F738C818DBAB3913F99CAF8F0F`; kernel log=`DC128D7CACF3516486574F9DF6F65B7CC5EB50875F75B30B160FACEC711CD31B`。
- version 8はreadiness 904秒で成功したが、version 9は1080秒で28/38 shardに留まった。起動I/O速度のrun間差があり、今回memory条件は一度も実行されていない。version 10 treatmentはpushせず、off対slim比較を不成立とする。同じversionの再試行はしない。
- 2026-10-23 23:03 UTC前後の正確なARC3 competition slug read-only照会でも履歴不変: `57541830 COMPLETE / 0.25`、`57527856 COMPLETE / 0.00`、両方private score未観測。Competition Rerun/公式提出なし。C:空き`1,167,060,992` bytes。

## 採否と次工程

C2-034のmemory仮説は未検証のまま保留。v9の出力でmodel shard読込遅延が実測されたため、次は一度だけreadiness deadlineを1800秒へ変更したcontrolを先行させるC2-035へ進む。controlがready・benchmark開始を満たさなければslim armを実行せず、同じmodel load deadlineの追加延長はしない。
