# 歴史的復旧archiveと公式接続の安全化派生物

## 目的・観測・原因・変更
目的は、回収できた過去の素材・状態・raw・sourceと、回収できなかった境界を保存すること。
復旧原archiveは196外側memberと1950memberの内包checkpointを持つ。公開記録3本637行2256frame、自己管理sourceと部分復旧記録を含む。保存先に原本が未統合だったため、完全manifestと独立検査を添えて非runtime運転記録へ保存する。

公式接続は原archiveそのものを採用しない。opaque stdout/stderr54本は本文を開かず除外し、二つのJSONにある輸送cookie header値だけを明示markerに置換した、別名の安全化派生物を保存する。1137member本文は原byte不変、変更2、追加説明2で1141member。除外置換manifestに原サイズ・hash・理由を記録し、cookie値そのものは載せない。原archiveは既存Libraryで保持し、この派生物を原本同一とは呼ばない。

## previous / current / delta / regression
previousは本commitの単一parent。直前までに保存された原archive12/14へ復旧原archive1本を加え、currentは13/14となる。公式接続の派生物は原本数に含めない。変更は証拠ファイル追加のみで、既存main全blobを不変に保つ。
deltaは一次証拠への到達可能性であり、能力向上ではない。両payloadのSHA256とgzip CRC/EOF、完全manifest、独立内容検査を照合。公式派生物は全1141memberの構成・hash、opaque不存在、既知cookie不存在を独立検査済み。HDS/authority/現在状態は変更しない。

## limitations
- 復旧archiveのさらに古い原hashは未取得。今回回収したLibrary payloadの同一性とmanifest閉包を検証した。
- Color3/Query3/Color12/Query1の完全な素材・状態・journal原ファイルと当時の実行状態は未回収。過去のPASS表示を原証拠の代用にしない。
- 内包goal-role checkpointはH A/B、Aremaining prefixes1–3、Query10の記録範囲。Paintingや外部依存を全て含むとは主張しない。
- native29489/fixture18870は未解決。fresh043と後期素材、358669Bの歴史解析も未回収のまま。
- 公式接続の25ゲーム初期観測27frameは全てcompleted0。metadata183は攻略数ではない。946行2110frameの公開鎖記録と165相の保存測定は、旧46教師への対応と完成label由来が未証明。
- 原FAIL、部分記録、synthetic fixture、旧source版を成功扱いにしない。認証済みfresh1/183と全game WIN未確認の境界は不変。
- すべて証拠保存。今回native HDS/Query/Teach/SDK/Actionは0、runtime採用なし。旧path参照は本文の同梱・実行権限を意味しない。

公式原archiveを含む全14本の原本保存、あるいは失われた全作業の完全復旧は完了していない。
