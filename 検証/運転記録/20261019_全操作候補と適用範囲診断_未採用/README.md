# goal6 の操作接続診断と適用範囲修正（未採用）

## 目的
既存の配色接続 source と歴史公開 packet を用い、goal6 の末端条件対応だけで操作を許可できるかを診断した証拠を保存する。結論は全候補 HOLD。成立したのは限定された pure 診断・不正入力拒否・証拠保存であり、新たな攻略能力や runtime 採用ではない。

## 観測
既存公開12行の全112 phase を扱い、35 phase の既存観測を再現し、77 phase は未解釈のまま残した。各phaseの Action1–5 と Action6 全4096座標を含む4101候補、合計459,312候補を省略せず記録した。全て HOLD、execution_permission=false。21件はphase局所の照会案で、native Query は実行していない。

## 原因
既存の予測・手順・応答 gate は COPY/MASK/TURN、器具形状、座標対応等の証拠を必要とし、goal6 の「固定幾何の修復保全条件組→公開末端進捗」だけでは閉じない。Action番号と役割、half-plane mask、12器具template、画像の構造認識は固定priorであり、今回学習した規則ではない。

初期 candidate() は利用不能Action5や不正な引数に対して照会案を返す欠陥があり、red component の最大要素選択にも役割曖昧性があった。当時も実行許可はfalseだったが、照会案の適用範囲は十分に閉じていなかった。

## 変更
v2 は利用可能Actionの厳密型・重複・キー集合・非click空引数・click整数座標と範囲を検査。v3 は全red component を調べ、最大同数や複数の妥当な器具候補を拒否した。固定構造の一意性検査であり、因果的なrole証明への昇格は行わない。初期source・probe・全候補・manifest、v2 source、初期reviewと追加reviewを別ファイルで保持する。

独立reviewの初回tuple/list比較 assertion failure は修正前runnerと説明が残るが、この閉鎖payloadには専用の初回traceback/stdout原物は含まれない。全失敗出力が保存されたとは主張しない。

保存前の内容監査でも、新問題phase15の分類名を別名と比較して200件の偽不一致を出した。元schemaの new_problem_unbound へ監査側比較を直し、全9,200 phase-cell viewで不一致0を確認した。payloadは変更していない。誤判定の全ラベル・訂正・原物の保存限界は payload_admission の admission_validator_corrections に記載する。

本commitは source側 MANIFEST_v3 の45件＋自身、review側 FINAL_MANIFEST_v3 の17件＋自身、計64原ファイル8,420,785 bytesを保存する。両版の候補gzipは元の圧縮byteも維持するため別々に収録する。派生pyc 11,772 bytesだけを未列挙cacheとして除外し、対応sourceは含めた。新規operation教師contractや未完了identity教師計画は対象外。

## previous
開始mainは93b9d0def82eddcd86626bb64ef06350b245d81d。v1診断は全112 phase/459,312候補を保持し全HOLDだったが、不正scopeで照会案を返した。最大red component を役割確定の根拠にできないことも初期reviewで指摘された。修正前の正確なsourceと再現probeが残る。

## current
15件の不正Action/availability probeは全て照会案なしのHOLD。追加の実frame由来の合成曖昧性2件（小さい妥当器具の追加、同サイズ器具の複製）も UnresolvedInstrumentRole、scene=null、照会案なし。これは新しい環境観測や教師ではない。

## delta
不正入力と器具曖昧性の拒否が強化された。正常歴史corpusのphase JSON全byteと、候補gzipを展開した全行byteは修正前後で不変。圧縮gzip自身のhashはヘッダ等で異なるため、展開結果の一致と圧縮原物の保存を区別する。

## regression
独立reviewは全112 raw phase と459,312候補を再計算し、全順序・Action・結果を照合。原archiveの接続source10件ともbyte一致。publisherも10件の原archive memberと13件の既存公開入力memberをhash照合した。原入力は既にmainの教師対照archive内にあり、origin_verification に再現可能なarchive/member参照を記載して重複bulkを避けた。新規native/SDK/Actionは0件。

## 画素帰属の成立範囲
6操作×100対象の600帰属行を保持。旧問題の末端phase13/14で固定maskとの一致が観測された。phase14の分類は mask内の識別可能な色変化210、mask外の識別可能な旧色保持240、元から器具色で識別不能150。case3は100/100が識別不能で、上書きとno-opの区別に正の証拠を与えない。画素やphaseを独立したAction実験数へ読み替えない。正例のphase15には参照bindingの変更があり、旧問題の保存と混同しない。

## limitations
全phaseの因果解釈、実Action番号と作用の因果対応、COPY/MASK/TURN の学習済みstateと支持証拠の歴史的接合は未確定。半面maskは教師を作った同じ仮説であり、学習済みmaskや唯一の成功条件ではない。旧公開記録は現在のfresh packetや実行権限にならない。phase() の出力は構造射影であり、candidate() のscope検査を通った実照会と見なさない。pure_dependencies 自体はmanifest検査を強制しないため、今後のpure source利用にも事前のhash照合が必要。

本保存・診断でnative経験数や原理数は増えない。直前の限定native学習結果189経験・1新系統3versionを一般化しない。認証fresh成功1/183（約0.55%）、full-game WIN未成立も不変。速度比較条件を揃えた改善試験ではなく、候補数やtest数を能力改善としない。中核・AGENTS・権限・現在状態・旧mainは無変更。以前の13/14原archive保存と公式派生物、未復旧fresh043等の限界も継続する。

## 検証順序
payload_manifest と archive_verification → 原producer manifest → pre_fix_v1 / pre_red_guard_v2 → all_phases / 全候補 → 初期review → FINAL_RECHECK_v3 を参照する。旧READMEの未修正所見は当時の原文として保持し、後続reviewが限定された修正確認を補う。TEACHER_PLAN.md は未実行の提案であり、教師投入やAction実行の成立証拠ではない。
