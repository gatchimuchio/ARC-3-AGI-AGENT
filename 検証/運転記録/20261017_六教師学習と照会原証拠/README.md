# 六教師の学習と同一六例への照会: 原証拠保存

- 目的: 公開教師からの歴史的学習と照会の状態・raw・source・失敗を追跡可能にする。
- 観測: 二つの原archiveの既知SHA256、248外側member、完全manifest、gzip CRC/EOFを照合。詳細は独立内容検査。
- 原因: 以前のmainは要約中心で、原archive本体が未保存だった。
- 変更: 原archive2本、完全manifest2本、独立検査2本、索引と本説明を非runtime運転記録へ追加。
- previous: 342677843cfeb415f3006e360da30e90349c5d04。319既存blob、回収した原archiveは7/14保存済み。
- current: 六教師学習・照会の原証拠を追加し、9/14原archiveを保持。既存ファイルは変更しない。
- delta: 学習側は二回の歴史的Teach6/Query0と全before/after状態・raw。公開12行112相を含む。照会側は同じ六教師へのQuery6/Teach0、正解6・wrong/missing/extra/HOLD各0。経験6不変で二つの照会counterだけ各回+1。
- regression: 原member/hash/manifest/CRCを独立検査済み。固定coreコピー14本は既存Gitと同一。今回の復元byteも同じ原archive SHAに一致。
- limitations: 六例は成功レベル数ではない。同じ教師への回帰であり、未見転用・学習されたAND因果・新clearの証明ではない。joint-keyは固定可逆符号化。認証済みfresh1/183、全game WIN未確認の境界は不変。

## 重複と欠落

照会archiveは学習archiveを内包する。原packageの同一性を保つため、外側二本をそのまま保存する。重複を新しい経験や独立支持に数えない。

古いnative29489の未閉鎖とfixture18870の失敗履歴は未解決のまま保持する。古い監査FAILと後のPASSを混同しない。外部の公開記録は別の復旧archiveへの参照を含み、参照先を無条件に同梱したとは主張しない。

全183レベル攻略、汎化、速度改善、runtime採用の主張はない。今回HDS/Query/Teach/SDK/Action実行は0。HDS中核・authority・現在状態は変更しない。公式接続の未審査opaqueを含む原archiveは別途保留で、全14本が完全保存済みとはしない。
