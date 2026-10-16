# 保存済み118観測の独立診断・原証拠

## 目的・観測・原因・変更

既存の集約報告に加え、保存済み118観測に対する診断の入力参照、raw Query、型付き応答、前後の標準状態、source、失敗、監査を原アーカイブのまま保持する。以前は概要・一部監査だけがmainにあり、元の作業directoryは再起動後に失われた。Libraryから復旧した最終配布版は既知のSHA256と一致した。

## previous / current / delta

- previous: `2fd7b6382337516aa70ec260e48126dcc09fc068`。原学習3本と新しい未採用/HOLD検証は保存済み。saved118は報告のみだった。
- current: 最終版 `saved118_diagnostic_v2_delivery.tar.xz`、完全な原manifest、今回の独立検査と索引を追加する。
- delta: 3,912通常ファイルと6directory、計3,918memberの原証拠がGitから取得できる。中断した別名のpartial archiveは最終成果物として使わない。

## 診断が示すこと

- 完了観測は番号0–117の118件。Queryは前半993件と後半767件、合計1,760件。
- 対になる識別子counterは4887 → 5880 → 6647。経験は183のまま。識別子以外の標準状態は不変。
- すべてのintent / reply / raw / external-output対、counterの各+1遷移を照合した。
- 前半runはFAILED・exit130。途中のframe59入力も残る。後半は別runとして補完した。集約監査が成立したことを前半run成功へ読み替えない。
- この診断にTeach・SDK・Actionの追加実行はない。183は経験でありクリア数ではない。

## regression

全memberの名前・サイズ・SHA256と外側XZのCRC64/EOFを照合した。内部XZ3,766本と空でないJSON3,856件をすべて検査し、1,047,874個の型付きdata形状を検証した。自作sourceは静的検査のみ。秘密情報、公式game/SDK実装や未分類のopaque bodyは確認されなかった。元archiveはbyte不変。

## limitations

- 観測診断は既存の保存入力に対するもの。新しいfresh実行・成功レベル・全ゲームWIN・汎化・速度改善を示さない。認証済みfresh成功1/183（約0.55%）を増やさない。
- 失敗の0-byte標準状態placeholder、前半の中断、旧 `harness_disabled_v4.py` のIndentationErrorと歴史的SyntaxWarningを保存する。失敗・古いsourceを採用runtimeへ組み込まない。
- 外部FileRefが指す未収録依存を保存済みとはしない。後続suffix入力closureの監査sourceは未復旧で、既存mainの報告以上の閉包を主張しない。
- fresh043のsource・実行証拠と一部後期資料は未回収。新しいHOLD再測定は、欠落した歴史的解析の代替原本ではない。
- 出版作業ではnative HDS・Query・Teach・SDK・Actionを実行しない。HDS、AGENTS、権限、現在状態、既存blobは変更しない。
- 他の成功・失敗archiveは保存作業を継続中。このcheckpointだけで全成果の保存完了とはしない。

`原診断索引.json` がarchiveとmanifestのSHA256を示す。gzip manifestを展開すると原manifestのJSONとbyte一致する。大容量archiveはconnectorから独立に全bytesを再取得できないため、remote Git blob SHA・treeサイズを検証する。小さいmetadataは全内容を読み戻す。
