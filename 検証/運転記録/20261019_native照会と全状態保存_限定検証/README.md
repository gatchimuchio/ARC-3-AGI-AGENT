# 保存済み公開観測による native Query / 全状態保存の限定検証

## 目的

凍結 HDS v0.4.2 と既存の意味・目標・保存条件経路を、保存済み公開観測一件へ接続した閉鎖済み Query/save 試験を証拠として保存する。学習・実ゲーム操作・能力向上の採用記録ではない。統合前 main は `32c2f6be80216e3685c022941c6a80a606e8442e`、試験開始時に固定された main は `06961ee02d43329aee746d763cf19d651f97bcaa`。

## 観測

- 実際の native Query は 13 回。内訳は役割 2、目標関係 2、操作対応 5、準備作用 4。この観測では修復・保存の Query は発生していない。
- 正常状態 5,355,957 bytes の restore/save は 3 回とも原本と完全一致。実 Query 後は全型・値・辞書順序・列順序・台帳・履歴を比較し、対になった照会／学習判定カウンタだけが 6647 → 6660。183 経験、16 原理と既存履歴は不変。
- 40 個の exact codec records（13 input、13 output、13 input_after、全意味結果 1）を、offset・長さ・SHA-256 と共に保存。使用領域は 251,453 bytes。全 input_after は input と一致し、9 個の実行許可フラグは false。
- 4 token / 4 slot の保存済み全観測を使用。入力 6,627 bytes、SHA-256 `ce4c2950ac1d3fd1abbd67bb84196397777d080f2f0c6258245be8241b25cdab`。24 対応付けを調べ、目標候補 1、構造的操作候補 5、作用支持 4 を得た。UNKNOWN の提出候補も保存されている。これらは行動許可ではない。

## 原因と保持した失敗

初回 Query 試験は、16 MiB の証拠領域を確保しようとして、既存の per-file 8 MiB 制限に抵触した（OSError 27）。正常状態の保存後、Query 開始前の失敗である。失敗した evidence.bin は 0 bytes のまま保持した。

per-file 制約の修正試験後、96 MiB の総量枠では残存失敗証拠と retry 全割当を同時に収容できず、次の試行は子プロセス起動前の admission で停止した。非ゼロの状態記録を含む既存の予約ファイルは再利用していない。明示された資源調整 96 → 112 MiB（差分 16 MiB）とその理由を budget_change.json に保存した。

最後の試行は exit 0、wall 1.7920 s、peak RSS 88,452 KiB。AS 512 MiB、compute 合計 120 s、finalization 120 s、最大 31 Query の枠内で 13 Query を実施。観測された小規模試行の数値であり、Teach の容量保証や速度改善ではない。

## 変更

この commit は `検証/運転記録/` にのみ、130 個の凍結入力・ソース・結果・失敗・独立監査を束ねた gzip tar と、索引・検証を追加する。archive は予約ファイルのゼロ領域も含む元の全バイトを通常の lossless gzip で保存する。prefix 抜粋や reserve の破棄ではない。展開時には元の約 94.4 MB を要する。展開やコード実行は、この保存 commit による実行承認を意味しない。

## previous / current / delta

| 項目 | previous | current | delta |
|---|---|---|---|
| 意味経路接続 | pure/mock 比較を保存済み | 保存済み観測一件で native Query/save を独立監査 | 13 実 Query の閉鎖証拠 |
| Query／判定カウンタ | 6647 / 6647 | 6660 / 6660 | +13 / +13 |
| 経験 / 原理 | 183 / 16 | 183 / 16 | 0 / 0 |
| native Teach / SDK / Action | この単位では 0 | 0 / 0 / 0 | 学習・実ゲーム操作なし |
| fresh 認証成功 | 1 / 183 | 1 / 183 | 0、full-game WIN なし |
| adopted runtime / core / authority | 変更なし | 変更なし | 0 |

## regression / 監査

独立監査 `独立監査.md` と verification.json は、34 個の入力・ソース・指示書 pin、12 個の凍結 HDS Python module、runner/guard/supervisor の実行時 snapshot、全 native codec 証拠、正常状態・全台帳・履歴、失敗 reserve の元バイトを検証した。publisher は原本を実行せず、130 ファイルと 34 source pins を hash 照合し、archive 全 member を読み戻した。

原運転の native trace は不採用 23 対応付けの集計を持つが、各不採用の詳細は未収録だった。独立監査は exact family grammar と記録済み role 応答から 24 行すべてを純粋計算で再構成し、採用 1 行と不採用理由の集計が原結果と一致することを確認した。`reconstructed_assignments.json` はこの事後再構成であり、元の runtime が各詳細を採取したという意味ではない。将来の実行では全対応付け・理由・HOLD を inline 保存する必要がある。

原本の README / delivery_manifest / final_gate_report の `REVIEW_PENDING` は当時の snapshot として無変更で保持する。その後の独立監査は、完了したこの Query/save 単位に限定して `BOUNDED PASS` とした。payload_manifest.json はその時系列を明示する。

## limitations

この一件は転用・学習効果・追加 level 成功・汎用能力を立証しない。固定特徴抽出・全対応付け列挙は既存 prior である。入力は保存済み公開観測であり、live Action の authority ではない。既存の unsupported-role / UNKNOWN-goal の診断上の弱さもそのまま保持している。

launcher はより大きい試行や Teach 向けに全面承認されていない。総量監視は race-free hard quota ではなく、metadata/log 1 MiB は合算強制上限ではない。emergency reserve には supervisor の状態だけが入り、任意の failure.json は新規容量を必要とする。mid-route failure の suffix 判定は route 戻り後の calls 値に依存し、実 Query に入った後でも全経路未処理と記録し得る。成功した今回の経路では発現していないが、別作業で修正・検証が完了するまで、これらを閉じたとは扱わない。

既存 main の保存範囲索引にある欠落（fresh043 後半、消失した歴史的分析 358,669 bytes など）を補完した記録でもない。13/14 回収原本の exact 保存と、official-connection 原本を保留して安全化派生物のみ保存した例外は継続する。全作業保存済みとは主張しない。

## ファイルと確認

`payload_manifest.json` が 130 元ファイルのパス・bytes・SHA-256 を固定する。archive 内 MANIFEST.json は保存された全 member を列挙する。`archive_verification.json` が archive の bytes / SHA-256 / Git blob と全 member 読み戻しを記録する。`payload_admission.json` はデータ内容とソースを実行せずに行った独立内容確認、`origin_verification.json` は元入力との一致を示す。元コードを実行せずに通常の tar/gzip/hash ツールで archive 全体と各 member の同一性を確認できる。
