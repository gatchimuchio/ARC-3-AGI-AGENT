# 呼出側の容量・失敗捕捉・全候補記録の pure 検証

## 目的

前の native Query/save 検証で残った呼出側の資源・失敗記録の問題について、閉鎖済み修正案と独立 pure/static 監査を保存する。統合前 main は `9674d79c3f6801619cb6fa620b93865ab7822e99`。HDS 中核、authority、現在状態、採用 runtime を変更しない証拠用 checkpoint である。

## 観測

独立監査は提供された 21 pure tests と独立 adversarial tests 2 件を通過した。変更前 native pilot の 126 ファイルは全数 hash 一致。全意味結果・13 個の記録済み応答・24 対応付け行（採用 1、不採用 23）との一致を確認した。これらの件数は能力向上や native 実行の証拠ではない。

## 原因 / 変更

前の launcher には、総量の計画値と実書込先の拘束が分離していること、failure.json が新規容量を必要とすること、mid-route 失敗で消費済み prefix を誤記し得ること、元の native trace が不採用各行の詳細を保存していないことが残っていた。

この修正案は、既存 bytes と全予約領域を入場時に計上し、既知の書込を固定領域に制限する。metadata/stdout/stderr は合算領域を使用。entered / returned / persisted を別々に追跡し、未確定 frontier は UNKNOWN とする。子の診断・緊急領域と親の終端領域を物理的に分離し、事前符号化した緊急 frame と原例外保持を追加する。候補列挙では各 match 直後に detached record を observer へ渡す。列挙順・選別・不採用条件・dedup・HOLD 判定は変えていない。

レビューの初期 probe は、fork 後に親の終端記録が子の fallback を上書きする問題を再現した。独立レビューは診断 encoding 失敗によって原例外を失う問題も報告し、最終 regression で修正後の保持を確認している。元の失敗 log・probe・reserve は削除せず保存した。

`fork_fallback/supervisor_failure.reserve` には有効な supervisor frame の後に、上書きされた子記録の JSON suffix 129 bytes が残る。この破損状態もそのまま保持し、正常な記録として読み替えない。

## previous / current / delta

- previous: 完了済み native 13 Query の証拠は保存済み。ただし caller-side の失敗・容量・inline 記録に上記制約が残っていた。
- current: caller-side の修正案が pure/static の限定監査を通過し、全 60 元ファイルを凍結した。既存 native pilot 126 ファイルと HDS は不変。
- delta: この単位の native Query / Teach / native save-load / SDK / Action はすべて 0。学習状態・経験数・原理数・certified fresh 1/183 に変化はない。

## regression

`独立監査.md`、pure_tests_final.log、adversarial_tests_final.log、reviewed_manifest.json に最終確認を保持する。publisher は 126 prechange pins、26 review pins、8 個の意味経路 source/derivative pins を照合した。ソースや test を publisher が実行することなく、全 member を内容確認し、archive を読み戻した。

guard_repair の README / verification.json の pending-review 表示は当時の snapshot として無変更で保持する。後続 guard_review の BOUNDED PASS はこの pure/static 単位に限定した判断である。

## limitations / 履歴欠落

重要な保存範囲の限界: 2 件のレビュー不具合を持っていた時点の `bounded_store.py` / `launcher.py` の exact source snapshot は、この閉鎖範囲には存在しない。`guard_before.py` は旧 native pilot の guard であり、その代用品ではない。fork 不具合には probes.py / probes.log / reserve が残る。診断 encoding 不具合の初回再現出力は今回の files にはなく、README の報告と最終回帰だけが残る。この欠落を後から再構成した source/log で埋めていない。

追加の history_audit 2 ファイルを収録した。修正者の探索結果、現在の 60 ファイルの hash、欠落の説明と機序の文章による再構成を含む。この文章は原 source の復元でも、初回 encoding 注入が実行された証明でもない。初回 probe の source に注入コードがあるだけで実行済みとは扱わない。

容量制限は監査対象の既知 writer に対する上限であり、OS 全体の quota や敵対的コード sandbox ではない。凍結 native persistence の Path.write_text は reserve を truncate し、物理確保を解放し得る。空き容量 floor は入場時の観測であり、任意の ENOSPC / kernel failure / allocator failure に対する完全保存保証ではない。partial 出力は保持し、exact frontier が分からなければ UNKNOWN とし、自動再開しない。

このレビューでは native binding の実 import / restore / save を実行していない。現 Guard / launch_native は Query-only の binding であり、Teach の経路・増加量・失敗時容量の承認にはならない。別の concrete workload に対する成長量・writer・入力・失敗保持の審査が必要。進行中の native Teach / teacher 準備ディレクトリは本 archive に含めない。

既存の回収原本 13/14 exact 保存、official 原本保留と安全化派生物の例外、消失した fresh043 後半等の未回収範囲は継続する。全作業保存済みとは主張しない。

## 保存の確認

payload_manifest.json は元 60 ファイル、payload_manifest_v2.json は追加説明 2 ファイルを加えた 62 ファイルを exact bytes / SHA-256 で列挙する。独立 payload_admission.json は元 60、supplemental_admission.json は追加 2 の内容確認であり、範囲を混同しない。元 native pilot の大きい全状態・reserve は前 commit の検証済み archive を参照し、重複収録しない。今回の小さい pure reserve は prefix とゼロ領域を全バイト収録する。archive 内 MANIFEST.json と外側 archive_verification.json が保存範囲と同一性を示す。
