# 公開268教示（明示起動専用）

本CLIは公開3原票から確定した242局所＋26HUD入力を、独立した空の現行HDS v0.4.2へ各1回投入する。現mainのdispatcherやruntimeからは呼ばない。原票JSONLや完成Action列をruntimeで検索しない。ID/SHAは教材出所・同一経験の検査にのみ使う。

## 入力と支持

`公開教師268.json.gz` は全268外部入力、投入順、全6186由来と3原票SHAを含む小fixtureである。元画像やraw JSONLのコピーはない。役割/相の複数由来を独立Actionの支持数に増幅しない。集約前の全由来は残る。同一原票SHA×境界×同一HDS入力は1教材であり、CLIも重複を検査する。268は独立した空系だけに投入し、既存stateへ加算しない。再実行はさらに別の空系を作るので、過去実行との支持は合算しない。

26 HUD教材は原3票の2186独立Action由来を集約したもの。全黒の末尾1相だけをAction応答1観測とし、相数・同じ画面の再送は経験追加にしない。可視HUD失敗境界の支持であり、全目標の必要十分性や外部counterの因果まで証明しない。未観測Actionや不足支持はHOLDを保持する。

固定知覚/幾何/文法と入力の由来は原学習freeze、r2順序freezeおよび接続API文書で明示した範囲に限る。公開原票の初期開始の出所証拠と、実collectorが発行したRESET待受の対応証拠は異なる。初見黒画面はid0/full_reset metadataだけでfreshとせずHOLD。

## 採用先repoでのコマンド

```
REPO=/path/to/ARC-3-AGI-AGENT
OUT=/existing/writable/new-output-directory
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$REPO:$REPO/HDS/学習系統/v0.4.2" \
 python "$REPO/検証/連動教示/公開教師を教示.py" \
 --output "$OUT/連動268.json.gz" --log "$OUT/連動268逐次.jsonl.gz"
```

保存先親directoryは先に作成し、state/logとも未存在の名前を渡す。既存先の上書き・追記・自動再利用はない。各入力、HDS全出力と全由来は逐次gzipへ保存する。全268処理後に外側gzipへ同型の全7fieldを省略せず逐次保存する。

## 保存確定と比較

保存順は全byte復号SHA検査、意味検査、無改変の標準core readerによる再読込、型付き全byte再符号化SHA検査、fsync、非上書きhardlink、directory fsyncである。原stateと新stateの時刻は異なる。比較用JSONにのみ、原stateから分類した4384具体leafの時点/対象期間端点を復元し、他の全内容を比較する。実HDS/state内の時刻は変更しない。任意の同名「時点」keyや原入力の値を除外しない。位置不正・型不正・意味不一致は失敗であり、成功確定しない。

4384は型付き経験/懐疑/原理/学習過程記録の時点2198と、台帳/状態履歴/原理履歴中の具体内部辞書時点・対象期間端点2186。全位置と原時刻はfixtureに含む。元stateのcanonical意味SHAは b3ea32b3abfa4f3c6ec95663778c5edfecf168ff80ff81a0827af7d80bf57d90。

途中保存・既存先・確定競合・意味不一致・標準再読込失敗・型/byte不一致・確定後dir同期失敗は、未完gzipや理由JSONを保持して失敗となる。dir同期失敗時は最終名が存在していても成功ではない。例外/逐次logも捨てない。理由JSONを書けない保存先では、その失敗自体を例外出力に残す。

## 試験

`test_保存境界.py` は10保存/例外境界を試す。証拠保存先は `ARC_PAIRED_SAVE_TEST_DIR`、未設定なら新しい一時directory。各再実行はUUID別の証拠を保持する。

`検証/test_連動実状態.py` は空・人工反証269・再教示268で全165前提と候補/HOLD、意味Memory不変を検査する。`ARC_PAIRED_TRAINED_HDS` と `ARC_PAIRED_CONTRADICTION_HDS` を各外部gzipへ設定する。未設定は明示skip。教材fixtureの外部指定は任意の `ARC_PAIRED_TEACHER_FIXTURE`。

このCLIは公開開発照合でありfresh実環境成功ではない。実collectorの事前pending永続化・正本commit・再起動復元は未接続。Action送信や既存gate緩和はない。
