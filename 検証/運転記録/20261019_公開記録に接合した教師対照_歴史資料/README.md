# 公開記録へ接合した教師対照と既存境界の smoke 入力

## 目的

既存の Learning Machine を使う次の限定試験に向け、回収済みの公開観測・歴史的 native 入出力・現在状態を照合した教師候補と対照を保存する。統合前 main は `bb5fe8168e3816556805c4932dc91ac9c4813f03`。これは閉鎖済みのオフライン準備とその監査であり、この commit による native Teach 実行や runtime 採用はない。

## 観測

1. 既存の列修復 control は 4 行。教師は現状態の経験 130–133 と完全一致し、出力は true / true / false / true。公開原記録の 59 行、全 58 操作判断と 1,530 after phases を照合し、全候補・不適格・HOLD・失敗を残した。適格教師は原記録の rows 169 / 171 / 173 / 190。
2. Goal6 候補は別系統で歴史的に使った 6 行の完全な選択 batch。FF→false、FF→false、TF→false、FT→false、TT→true、TT→true。4 非進行・2 進行を、重複も含め保存した。全 status は NOT_FINISHED。2 本の公開記録全体の hash、選択 12 行の元 bytes/offset、全 112 frames を確認。phase の意味解釈は 35 measured / 77 unknown。
3. 既存 9 境界について、それぞれ一つの歴史的 native Query intent と一致する smoke 入力を追加した。runtime 入力は 2,659 bytes、SHA-256 `15e83ab6a7caacdcaf62c1585eef3f450de1bd6abc9da78276de9b0d45cec44c`。18 個の圧縮 intent / reply 原本、全候補 inventory、予測・HOLD 理由・provenance も残した。

## 原因 / 意味の限定

旧 control の「raw source join 未発見」という初期表示は、後の回収・独立照合より前の記録だった。元ファイルを変更せず、existing_four_row_control_v2.json が元 SHA を指定して supersede する。元 MANIFEST.json と全 156 files は不変で、MANIFEST_v2.json が追加分を含む 183 files を固定する。

列修復の input は、実際に選択された token とクリックされた唯一の空 slot の対応が、既存の feasible-goal set の少なくとも一員に適合するかを問う。output は末相で空 slot 数が減り、feasible-goal set が非空であることを示す。全 phase を通じた保存や必要因果を証明したものではない。独立監査は保存済み public-derived scene / goal sets から eligibility と projection を再計算したが、control の全認識・列挙を raw pixels から新たに導出したわけではない。

Goal6 の input は固定 half-plane / overwrite 仮説の下での「全未一致 cell を public reference に一致させる」「全既一致 cell を保存する」という対の JSON 文字列。output は public score after > before のみ。mask membership、Action5 の wide-paint role、frame 認識・列挙は既存固定 prior であり、6 教師が学習する機構ではない。2 つの正 endpoint は reference binding が変わり、77 phase は unknown のまま。geometry の正しさ、連続保存、前提の必要性・十分性、hidden-delta 不在、一般的 Action 安全性は成立していない。

## 変更 / previous / current / delta

- previous: 原学習・公開記録の archive は main に保存済み。control の初期表示は古く、次の限定試験用の exact 対照と回帰入力が未整理だった。
- current: 4 行の既学習 control と 6 行の歴史的 endpoint 候補を公開原記録へ接合し、9 境界の歴史的 smoke 入力を凍結した。元資料 187 ファイルを収録。
- delta: 新しい独立観測は 0。native Query / Teach / SDK / Action はこの準備・保存単位では 0。183 経験・16 原理、certified fresh 1/183、full-game WIN 未成立は変わらない。

現在の 183 経験 descendant に Goal6 の exact boundary が見つからないことは静的な状態照合であり、実際の before Query が HOLD するという結果ではない。別状態で歴史的に学習した事実を、現在状態での新しい before/after 成果に読み替えない。

## regression / 監査範囲

独立 witness 監査は元 156 files、公開原記録の全体 hash、全 raw joins、6 行の public-score labels、4 control 教師と経験 130–133 の一致を確認した。追加 MANIFEST_v2 の 9 smoke queries は後続の凍結入力であり、元の独立 witness 監査が全追加分を実行したという意味ではない。今回の内容確認は 187 files と追加 intent/reply の同一性・provenance を検査しただけで、native の再試験はしていない。

nine_expected_historical.json は比較用に native tuple を JSON list に正規化している。exact typed replies は 9 個の reply_*.json.xz に別途保持する。型や順序を検証するときは原 codec record を用い、正規化した値だけを全型一致の証拠にしない。

9 件は各境界一例の smoke 検査用であり、全値域の無回帰や過去の fresh 成功保持を立証しない。将来の実行では current descendant の exact before/after 応答・HOLD・conflict・applicability、全既存履歴 prefix の保存、新しい支持/反証/原理変化を実測する必要がある。historical reply は参照値であり現在の結果を保証しない。

## limitations / 未保存の履歴

独立 witness レビュー README は初期の syntax typo と typing annotation 環境不足による失敗 2 件に言及する。しかし今回の review は最終 source、最終 JSON、README の 3 ファイルだけで、当該 raw failure logs と当時の source snapshot は含まれない。存在しない bytes を後から作って原記録と呼ばない。

6 行は数学的最小教師集合でも全 Action5 の網羅証明でもない。6 matched queries は 4 種類の training-condition string に対応するため、exact endpoint mapping の取得を調べられても held-out 一般化や cross-game 因果転用にはならない。別報告の失われた歴史的分析 358,669 bytes の代用品でもない。

native Teach の増加量・完全保存・失敗時容量・実 binding は別の入場審査対象であり、この準備の RSS や過去の別状態の増加量をその保証に用いない。進行中の arc-native-teach-20261019 その他の未閉鎖資料を収録しない。hidden delta は観測不能なまま保持し、SDK/Action への自動遷移はない。

既存の 13/14 回収原本 exact 保存と official 原本保留・安全化派生物の例外、fresh043 後半等の未回収範囲も継続する。全作業保存済みとは主張しない。

## 保存範囲と参照

payload_manifest.json は元 187 files の exact bytes / SHA-256 を列挙する。manifest 外の生成 cache 1 ファイル（inspect_state.cpython-312.pyc、2,617 bytes）は除外し、対応する inspect_state.py は保存する。既に main にある goalset4 / CP3 / prepsave / 歴史復旧の archive 原本は再収録せず、origin_verification.json に repository path・Git blob・SHA-256 を記録した。公開 raw rows、全 phase delta、exact intents/replies は本 archive に実データを収録する。

archive 内 MANIFEST.json と外側 archive_verification.json が全 member 読み戻しを記録し、payload_admission.json が内容確認の範囲・限界を示す。元コードの実行を伴わず通常の gzip/tar/hash で bytes の一致を検査できる。
