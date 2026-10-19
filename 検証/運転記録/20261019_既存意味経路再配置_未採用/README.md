# 2026-10-19 既存意味経路の再配置（未採用）

## 目的・観測・原因・変更

既存の公開 frame → 固定 family 観測 → role/goal → 全 goal pool → 構造的作用候補 → mapping/effect/preservation 照会の経路を、新しい依存注入先へ移した際の同等性と境界を保存する。新しい solver や学習則を作った成果ではない。原本の絶対 path loader を実行しなくても、選択した既存関数を明示的な依存で検査できるようにした。

観測された成立範囲は次の通り。

- 192 件で、型・順序を含む全結果、照会入出力・順序・予算、mock memory が原本と一致。
- terminal・unsupported・malformed の追加 3 件は traceback の path/line 表記だけを正規化して一致。元の双方の traceback を残し、全文 byte 一致とはしない。
- 追加 8 edge cases と、別 worker の literal oracle による 32 probes を保持。独立レビューは限定的な再配置同等性として PASS。
- 保存済みの公開入力 25 packets / 27 phases の hash を確認し、限定診断用の一つの whole packet を選んだ。選択 packet の既存意味経路は 24 割当、1 goal、5 構造候補、13 mock 照会で一致。これは公開 frame の解析と接続形状の確認であり、native 判断・学習・成功の確認ではない。

原因は、既存の意味経路が歴史的な絶対 path と起動処理に結び付いていたこと。変更は依存注入を明示した再配置と、その元 source・生成手順・比較結果の証拠保存である。選択関数の AST 一致と preservation source の byte 同一性を維持し、policy を黙って置き換えていない。

## previous / current / delta / regression

previous は main `06961ee02d43329aee746d763cf19d651f97bcaa`。一手 mock の保存・判断束縛試作は既に別 checkpoint として保存されている。

current は完成済みの意味経路再配置・独立レビューを非 runtime 運転記録へ追加した状態。delta は 36-file delivery、delivery manifest、および追加レビューを含む独立レビュー 11 files の実体保存である。後続の native Query 作業は進行中のため含まない。

regression は 36 delivery pins と 13 origin/authority pins の byte/hash 照合、原本対再配置の限定比較、独立 literal oracle と raw trace で追跡する。既存 main の 360 blobs、HDS、中核、AGENTS、権限、現在状態は不変。学習経験・攻略能力の増分はない。

レビュー時点の境界も保持する。`reviewed_hashes.json` が記録した公開入力 test は旧 3,869-byte 版で、その同一 byte は `reports/public01/check_saved_public_inputs.py` に残る。現行 `tests/check_saved_public_inputs.py` は 3,845 bytes で、比較を `pack(normalized(...))` から `pack(...)` へ厳格化した差分がある。追加の `supplemental_public_strict_review.md` と `public_strict_current/` が、現行の正確な hash に対する独立再検査 PASS と raw 結果を記録する。旧レビューと hash 記録を上書きして同一時点の検査だったようには扱わない。

## 保存物

`arc-semantic-rehost-checkpoint-20261019.tar.gz` は `payload_manifest_v2.json` に固定した 48 ファイルと包装 metadata を収録する。元ディレクトリ名を保ち、全 member の byte 数・SHA256 を `archive_verification.json` で検証する。原本 source、最初の runner、raw trace、失敗境界 probe、独立レビューを含む。元の 44-file manifest と内容検査は保持し、追加 4 ファイルは別の補足検査で追跡する。

既存の大きな基底 state・公式 archive は重複同梱しない。参照先は `payload_manifest_v2.json` に main path と blob/hash を記載した。7 本の小さな自作 source 原本は、独立比較を再現するため同梱する。同じ hash の繰り返し trace は元の由来を保持するためそのまま残し、追加の独立支持には数えない。

純粋比較の再検証は同梱 `arc-semantic-rehost-20261019/README.md` の手順を使い、新しい出力 leaf を選ぶ。公開入力の再検査には記録された安全化公式 archive、由来確認には Owner/権限参照も必要である。履歴の絶対 path は任意の配置で動く保証ではない。本保存作業は target source を実行しない。

## limitations と保持した失敗境界

全 execution permission は false、NOT_ADOPTED。役割の support 参照欠落や、goal relation の dispute / UNKNOWN 状態を元経路が許す例が独立 probe で再現された。再配置も同じ挙動である。これは元の接続・証拠境界の欠損候補であり、HDS core の欠陥と断定しない。候補全体の採否だけでは Action 許可にならず、今後の別 binding は role/goal/mapping/effect/preservation の各 native 返値と支持・HOLD 条件を fail-closed に検査する必要がある。

完全列挙の主張は既存の限定構造文法の範囲内であり、25 game や全 pixel 解釈の網羅ではない。固定寸法・有限/反復列・保存操作 class は prior のまま。unsupported 候補と個別 HOLD を捨てず、実行しない。

native HDS/restore/Query/Teach、SDK、live Action はこの再配置・レビュー・保存工程で実行していない。純粋 mock の回数、AST 一致、test 数を学習・転用・速度・新規成功の証拠へ読み替えない。歴史的 1/183、183 経験・16 原理・counter 6647 はこの unit で再測定していない。native roundtrip・資源と障害保存、実教師由来、判断から Action への全証拠束縛は別 gate である。

`native_pilot_gate.md` は作成時点の次工程提案であり、本 checkpoint の実行許可・実施結果ではない。欠落した fresh043 と歴史解析を復元したとも主張しない。
