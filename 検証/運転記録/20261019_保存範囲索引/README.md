# 保存範囲と未回収境界（2026-10-19）

回収した原archive14本のうち13本、合計75,084,290 bytesをmainで追跡できる。計算期限失敗の原archiveは、輸送上限のため二つのbyte範囲partで保存し、順序連結で原byte数・SHA256に一致する。これに公式接続の安全化派生物1本と、復旧基底・保存失敗捕捉の未採用試作・公開教師再測定HOLDの新規package3本を別枠で保存した。

これは全作業の完全復旧や14本すべての原本保存を意味しない。公式接続の原本はopaque出力と輸送cookieを含むため保留。派生物は54member除外・2 JSONのcookie値置換を明示し、原本と区別する。原本そのものはLibraryで保持する。

## 目的・観測・原因・変更
目的は原本、派生物、重複、欠落と能力境界を一つの索引で追跡すること。観測対象はpayload commit82b4a51b7a49d0bd33549737b41e7b4e6a6a543dの350blob。再起動で作業環境が繰り返し失われたため、既存Libraryとmainから同一性を検証し保存を再開した。今回の変更は本書と機械可読索引だけ。

previousは上記payload commit。currentは保存範囲索引を追加したcommitで、原本数・能力値・runtime採否の増分はない。deltaは各原本のGit path/SHA/size、元SHA256、導入commit、除外・重複・未回収範囲の一元化。regressionとして整理開始前9ce18304の既存244blobすべてのSHAとmodeが現在も一致することを全数照合した。HDS、中核、AGENTS、authority、現在状態は不変。

## 証拠への入口
- [13原本と派生物・新規packageの完全索引](保存範囲.json)
- [129→133→183経験の原学習証拠](../20261016_原学習証拠/README.md)
- [118観測の診断raw・状態・失敗](../20261016_保存118観測診断原証拠/README.md)
- [最初のfresh成功の原証拠](../20261016_最初のfresh成功原証拠/README.md)
- [保存期限・計算期限失敗とpart復元](../20261016_保存計算期限失敗原証拠/README.md)
- [六教師学習と同じ六例への照会](../20261017_六教師学習と照会原証拠/README.md)
- [目標曖昧性の失敗三巻](../20261019_目標曖昧性失敗原証拠/README.md)
- [歴史復旧と公式接続の安全化派生物](../20261019_歴史復旧と公式接続派生物/README.md)

## limitations
認証済みfreshは1/183（約0.55%）。183は現在の経験数でもあり、183レベル成功ではない。全game WINは未確認。失敗runの6/8表示、教師recording内のWIN、同じ六教師への回帰、テスト件数を新規成功へ読み替えない。学習対象は目標に対する準備・実行可能性修復・保存条件で、固定特徴抽出や全bijection列挙はpriorのまま。

fresh043、後期source/launch証拠、358669Bの歴史解析、一部古い素材・状態・journalは未回収。公開教師再測定は新しいHOLD契約であり、その歴史解析の復元ではない。古いnative29489/fixture18870も未閉鎖。複数archiveの重複を独立支持や観測数の増加に数えない。

大容量ファイルのremote全文byte streamはconnector制限により取得できない。検証済みlocal byteのGit blob SHAとremote treeのSHA/sizeを照合し、1MiB以下のファイルは全文readbackも行った。圧縮ファイル名やhash参照だけでなく、上記13本の実payloadをmainに保存している。

CIは既存から続くrunner未割当・steps空でのfailureを確認している。テストが走って失敗したとは言えず、原因は未確認。今回の保存でnative HDS/Query/Teach/SDK/Actionは実行せず、試作をruntimeへ採用していない。
