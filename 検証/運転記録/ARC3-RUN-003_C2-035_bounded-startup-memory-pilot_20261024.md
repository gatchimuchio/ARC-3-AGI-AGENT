# ARC3-RUN-003 C2-035 実行記録（追記専用）

## 2026-10-24 JST：準備・control開始前

- 根拠はC2-034 version 9の実測：1080秒時点で28/38 shard、推論ready未確認、offline benchmark未開始。失敗ログはC2-034記録に保存済み。
- Kaggle model-guided kernel version 9は`ERROR`。C2-035は新しいtask・新しいNotebook SHAで、同じversionの再試行ではない。
- v10 control Notebook SHA-256 `944b110ec5dbd204f3906d614e8c94ecfd95e0b92e3e1fec2fd8de2c32912429`。v11 slim Notebook SHA-256 `1f8caafb2c8060d513c01e4fc4b6ea9d4e5d0bba1a7a3f4ebe55f21734624741`。両Notebookはnbformat validate PASS、arm間差分はcell 5の`ARC3_MEMORY_SECTIONS`のみ。共通startup deadlineは1800秒、seed0、3ゲーム、160 Action/game、1200秒/game。metadataは同一でprivate/GPU enabled/Internet disabled。
- C2-035のcontrolをready・benchmark開始まで確認後にだけtreatmentを実行する。両armが完了するまでC2-034由来のmemory仮説の採否は未決。
- 現行Git基底は`8667e9b9512e328084050007d3bdedb1ae5e245f`、branch `main`。既存dirty worktreeを保持し、stage/commit/resetなし。

## 継続状態

version 10 controlはまだpushしていない。次の操作はprivate controlの一度限りのpushとread-only status/log追跡。公式Competition Rerun・提出は行わない。

## 2026-10-24 JST：version 10 control結果

- private kernel version 10 statusは`ERROR`。kernel logに`DEADLINE after 1800s from server launch; server inference readiness was not confirmed`、offline benchmark未開始と記録。version 11 treatmentはpushしなかった。
- 取得した`serve.log`の最終weight行は`92% / 35 of 38 shards / 28:59 elapsed / estimated 02:43 remaining`。ready・action・level・memory updateは未観測。残りshardの推定所要時間がdeadline後まで続く見込みだったため、C2-035の条件どおり止めた。
- SHA-256: `serve.log`=`46CA97A7CFE418394C89074CB231A0C8DCD441B07AC1A9BF1C7DF8E15CABADED`; kernel log=`6588C4C2A985B31DD7A4D09868E3D66BE9882A21CB0406D3852338E1569EEF4C`。
- 1080秒では28/38、1800秒では35/38まで進んだが、どちらもreadiness deadline内にbenchmarkを始めなかった。timeout調整だけでは必要な比較を成立させられなかった。追加deadline延長・treatment実行なし。model memory仮説は未検証。

## 採否・継続先

C2-035はstartup feasibility不成立で閉じる。これ以上同一modelのcold-start deadlineを拡大せず、C2-034/035のprivate model branchからv3の公開HDS/runtime改善へ戻る。official candidate/Notebook/公式提出は変更なし。
