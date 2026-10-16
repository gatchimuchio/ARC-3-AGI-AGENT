# 最初のfresh 1レベル・原証拠

## 目的・観測・原因・変更

2026-10-13に成立した最初のfresh成功の記録を、報告だけでなく観測・raw呼出し・状態・実験source・監査まで原アーカイブで保持する。再起動後に失われた作業directoryの代わりに、Libraryから復旧し既知SHA256と一致した原配布物を保存する。今回の作業は再実行ではない。

## previous / current / delta

- previous: `feed4a1e46e3b9b72c3ed933d8abcc0415dfc6a0`。学習3本とsaved118の原証拠等は保存済み。first-freshの原archiveは未保存。
- current: 原archive、完全な原manifestのgzip、索引、独立内容検査を追加。
- delta: 2,126通常ファイルを原本のままGitで保持する。認証済みの歴史的境界は1レベルのまま。

## regression

全memberの名前・サイズ・SHA256、外側gzipのCRC/EOF、内部XZ958本、JSON2,021件を照合した。自作Python69本は静的検査のみ。公開palette画像262枚と小さい合成fixture3件を分類した。固定HDS14ファイルの複製は既存mainのGit blobと一致する。

SDKと名前にあるJSONは自作metadataであり、公式game/SDK実装やopaque stdout/stderr本体は含まない。参照先のbodyを追跡していない。

## limitations

認証済みfresh成功は1/183レベル（約0.55%）。後続の失敗runにある進捗をここへ加算しない。全game WIN、汎化、速度改善、新しい成功数を主張しない。固定特徴抽出・列挙はpriorであり、学習方策の証明としない。

過去source、pure fixture、HOLD、失敗、空のownership placeholderを削除しない。archiveの保存はruntime採用・native実行許可ではない。今回HDS/Query/Teach/SDK/Actionは実行せず、HDS中核・権限・現在状態・既存blobは変更しない。fresh043と後期資料の欠落は未解決。

大容量archiveはGit blob SHAとtreeサイズでremote内容identityを確認し、metadataは全内容を読み戻す。connectorから大容量archive全bytesを独立stream取得したとは主張しない。他の原archiveは引き続き保存中。
