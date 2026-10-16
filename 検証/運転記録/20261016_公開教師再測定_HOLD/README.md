# ARC3 公開教師の新規オフライン再測定（2026-10-16）

## 結論: HOLD / runtime未採用

公開画素からの限定された検証は成立した。歴史的解析ファイルの復旧や全フィールド整合の証明ではない。HDS復元・Teach・Query・SDK・Action・新規クリアは実行していない。能力向上は主張しない。

- 117診断: PT行1–59、LS行168–225。直前行の末相をbeforeとして使用。
- 2,900応答相を全保持。画素ハッシュ、順序、行byte offset/size/SHAを原PT/LS資料と照合。
- 21,910件のbefore充填枠×応答相の位置・記号を保持。枠の省略・重複なし。
- 別枠の教師50投影: 準備20、保存30。35元Actionに相関し、15Actionが重複。独立50試行ではない。
- 教師入力50/50・結果50/50が一致。準備26相、保存120相を全検証。
- 知覚可能2,471相、知覚UNKNOWN429相。UNKNOWNをfalseにしていない。
- 生画素での充填保存: true2,362相 / false109相 / unknown429相。
- 適用範囲込みの充填保存: true632相 / false105相 / unknown1,290相 / non-applicable873相。後者は公開進捗で旧問題が終了した相。構造変化・知覚不能はunknown。元の生画素判定も別欄に保持。
- 最終フィールド照合: match21,573 / unknown4,874 / non-applicable2,619 / mismatch0。これはフィールド検査件数であり相数でも能力数でもない。未解決フィールドはunknownのまま。

## 未解決事項

1. 歴史的goalset_preparation_preservation_analysis_v1.json（358,669bytes、SHA256 a86fb6da4582d5e8db24032cef2fa8f1a661fe55ca48ca2e8643a9ef5faffd85）の原bytesは未入手。元pathは作成していない。新成果の名前・schema・consumerは別物。
2. 同ファイルproducerのbroad_preservation_beforeの正確な定義は未入手。初回全件測定でPT53に差分（選択済在庫で既充填枠をクリック）が生じた。既存commonの準備/修復適格の和による候補値は記録したが、歴史的定義の証明には代用しない。全117件の当該比較をunknownとし、全体HOLDを保持。
3. 保存教師30件の結果はすべてpositiveであり、負の適用境界や汎化を証明しない。固定知覚・役割対応・全列挙は既存priorの範囲。

## ファイル

- evidence/public_prepsave_remeasurement_20261016_v1.json: NEW canonical evidence。10,301,872bytes、SHA256 59af9bc4a0dc04bdf8b6c84e5001f946eed25be9d47cb3f85f58f4522452f797。
- evidence/new_consumer_contract_v1.json: 別契約。全行・相・画素・before充填枠identityをpin。runtime_admission=false。
- source/remeasure_v1.py: 標準ライブラリのみ。既存family/commonから検査済の純関数ASTだけを分離。whole moduleはimportしない。
- source/consumer_contract_v1.py: オフライン整合・完全性検査。独立した意味再計算ではない。runtime採用要求は常にHOLD。
- inputs/: 元teacher pack、LS解析、59PT packet、既存自作source4本のbyte同一複製。元catalogのmissing-file gateは変更していない。
- evidence/immutable_inputs_verification_v1.json: 権限原文3、復旧main29、復旧自作source154、使用archive4、計190件が既存pinとbyte一致。
- evidence/reproduction_comparison_v1.json: 全corpus再走査による2回のcanonical出力がbyte同一。
- evidence/regression_v1.json / .log: 17件成功、失敗0、例外0。相省略/重複/順序違い、充填枠省略/重複、不正画素、背景/選択曖昧性、unknown/non-applicable、途中false、runtime拒否を検査。
- evidence/independent_review_v1.md: 読取専用の独立レビュー。

## 失敗・過大な仮判定の保存

- source/remeasure_incomplete_0747.py: 中断時の未実行source。
- preliminary_run_1: pack内raw-row pinが全117件にあるという誤仮定でKeyError。log/failure/sourceを保持。
- preliminary_run_2: LS候補集合をdictと仮定しTypeError。log/failure/sourceを保持。
- preliminary_run_3.json.gz: 全117件測定。target_slotsのdict対[position,token]という60件の表現差と、PT53の広義適格1件差を保持。全60件の位置と記号は損失なく対応する。
- preliminary_run_4.json.gz: 既存common scope候補が歴史値と一致したため強すぎる完了labelを出した仮報告。歴史producer未確認のため採用せず、最終HOLDが優先する。元bytesは保存。
- preliminary_reproduction_v1.json.gz: 最終canonicalとbyte同一の再実行出力。

## 再現と資源

Python標準ライブラリで source/remeasure_v1.py に未使用の出力名を渡す。evidenceは排他新規作成で既存結果を上書きしない。元のarc-preservation-recovery-20261016/archivesが同じ親directoryに必要。raw corpusはtar streamから全67,880,086bytesをhashし、必要行のみparse。67MB raw fileは展開しない。

固定上限: workdir24MiB（配布archiveを含む）、RLIMIT_AS512MiB、diskfloor1GiB、1run600秒。最終実行約9.16秒、最大RSS168,288KiB。時刻・実行時間・資源値はcanonical本体から分離。

source/consumer_contract_v1.pyのinspect_for_offline_evidenceに新成果と新契約を渡す。これは保存資料の確認だけを許可し、欠落している歴史原票の検査を迂回しない。
