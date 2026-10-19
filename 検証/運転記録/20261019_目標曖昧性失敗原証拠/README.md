# 目標曖昧性による停止の原証拠保存

## 目的
2026-10-13 の失敗運転 087b258ca57e41ff82229797bd8035b4 を、欠落・成功への読み替えなく保存する。既に独立監査で保存採用済みの三つの分割原本を変更せず収録し、原本同一性と完全目録を追跡可能にする。実行経路への採用、攻略再開、能力改善の主張は含まない。

## 観測
歴史的記録は Action 90、Query 2,234、Teach 0、通常状態 93、公開応答 phase 1,812、実 exit 1 の failed_closed である。step 90 の 13 Query、意味処理、照会後状態は完了しているが、最終採用・dossier・Action 91 は行われていない。公開表示 6/8 は途中経過であり、追加の認定成功ではない。原因監査の 328 phase と運転全体の 1,812 phase は範囲が異なる。

## 原因
step 90 で五つの目標候補が異なる frame 割当・具体的操作効果を持ち、完全目標の一意性 gate が ValueError で閉じた。非同値な五候補を同一目標として扱わない。失敗報告の汎用的な「残候補」表現を、未返却 Query がある証拠に読み替えない。

## 変更
- 三つの .tar.gz 分割原本を、独立監査時と同じ byte 数・SHA256 のまま保存する。
- 元の完全目録 manifest_v1.json と各巻の完全目録三つを、内容を変更せず決定的 gzip として添付する。gzip は mtime=0、元 filename なし、圧縮 level=9。圧縮表現だけが今回の派生物である。
- 既存の各巻独立監査三件と batch closure 一件を無変更で添付する。
- 本説明と原本同一性索引を追加する。runtime、Learning Machine、規範、現在状態は変更しない。

## previous
基準 main は 48fea6d044d466daad2a000122db7e95d592356e、tree は 8b2608c9fa63578b8922e8b26157ca83bd3480ff、既存 blob は 327 件。親作業で確認された保存済み原本は 9/14。今回の三巻は独立監査済みだが、この基準 commit には未収録。

## current
今回の追加対象は、同一の失敗運転を分割した原本三巻、完全目録 gzip 四件、独立監査四件、README と原本同一性索引の計 13 file。これら三原本の repository 保存と ref の確認が完了した時点で保存済み原本は 12/14 となる。ローカル準備だけを公開完了とは扱わない。

## delta
保存対象原本は +3、9/14 → 12/14（今回の commit 完了を条件とする）。歴史的認定 fresh 成功は 1/183 のままで、今回の認定増分は 0、full-game WIN の新規確認も 0。三巻を三運転・三成功に数えない。公式原本は引き続き保留であり、別途の sanitized 派生物を 14 番目の原本として数えない。

## regression
今回実施した検査は保存同一性検査である。三原本の byte 数・SHA256 を既存独立監査と再照合し、全 gzip の CRC と EOF を確認した。元の完全目録と各巻目録は原文 byte 数・SHA256 を照合し、gzip 化後の再展開で同一性と CRC/EOF を確認した。既存監査三件は batch closure 記載の byte 数・SHA256 と一致する。規範六件も既存 closure 記載の hash と一致する。

内容の全意味監査は、同一 SHA256 の原本に対する既存独立監査を引き継ぐ。今回その監査を再実施せず、新しい native HDS、SDK、Query、Teach、Action、fresh、replay、回復コード実行、能力回帰試験は行っていない。Git と upload はこのローカル準備作業では行っていない。

## limitations
三巻を合わせた論理閉包は、既存 batch closure により元の 6,755 member（payload 390,434,744 byte）の欠落・size/hash 不一致 0 と確認されている。元の完全目録自体を含む一意 payload は 6,756、巻ごとの物理 member は計 6,763。共有 checkpoint と元目録には同一内容の重複があり、三つの巻目録が付加されている。

分割前 tar.gz の申告値は 22,304,243 byte、SHA256 93dd03fc79465d07ae0604e91c9a52f2eca1546549f8ca9f3d6377297ba76fec だが、その圧縮原本を今回取得・再構成・独立 hash 検証したとは主張しない。論理 member の閉包と分割前の圧縮 byte 同一性は別である。各巻だけでは完全な運転記録にならない。

既存監査の未解決 security/PII/opaque candidate は 0 だが、任意符号化された秘密や全識別子が存在しないことの数学的証明ではない。SDK 名を持つ自己生成 metadata の参照先、公式実装、opaque stdout/stderr/cache は開いていない。任意 Python heap や全外部依存の復元可能性も保証しない。

## 内容への入口
- [原本同一性索引](原本同一性索引.json): 三巻、完全目録、監査報告の byte 数・SHA256・Git blob identity と限界。
- [既存 batch closure](独立監査/independent_success_failure_batch_closure.json): 三巻の論理閉包、失敗境界、独立監査の根拠。
- 原本/ 以下: 無変更の三巻。
- 完全目録/ 以下: 完全な原文 JSON の gzip 四件。要約目録ではない。
