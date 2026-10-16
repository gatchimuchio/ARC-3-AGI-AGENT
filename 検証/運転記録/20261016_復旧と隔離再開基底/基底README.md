# ARC3 隔離再開基底 2026-10-16

## 結論

最新の回収済み閉鎖状態と必要最小限のソースを、別ディレクトリへバイト単位で復元した。
復元・検査スクリプトは実行可能。旧診断や live 接続を実行できる状態とはまだ言えない。
HDS の import、native 復元、Query、Teach、SDK、Action は実行していない。

- 復元済み: 24 ファイル、5,546,099 bytes
- 閉鎖状態: `state/after_all_queries.standard.json`、5,355,957 bytes
- 状態 SHA-256: `5b0550a80f1981e5fa8200409e3454cb5916349f0d38cc7b28068d01017e5f09`
- シリアライズ済み台帳: 学習経験 183、原理 16
- シリアライズ済み識別子: 照会 6647、学習判定 6647
- 183 は経験数であり、183 レベルの成功を意味しない
- 凍結 HDS v0.4.2: Python 12 ファイルと README/pyproject、合計 14 ファイル
- 接続側の自己作成ソース: 9 ファイル

現在の公式成功数・能力改善・game 間転用を、この復元・検査から主張しない。

## 根拠と保存配置

`pins.json` に旧絶対パス、archive/member、bytes、SHA-256、新しい相対配置を全件記録した。
HDS 14 ファイルは saved118 manifest の externalFileRefs と照合してから、
`ARC3_目標相対操作学習_20261013_v2.tar.gz` から取り出した。HDS の内容は変更していない。

状態は `saved118_diagnostic_v2_delivery.tar.xz` 内の
`arc-column-live-loop-20261013/evidence/76fb30b532aa412bab83d5aa1cd6df23/after_all_queries.standard.json`
から取り出した。最新の未回収 fresh043 状態を再現したものではない。

旧配置からの対応は次のとおり。完全な対応は `pins.json` を参照する。

- `arc-recovery-main-20261013/repository/HDS/学習系統/v0.4.2/` → `frozen/HDS/学習系統/v0.4.2/`
- `arc-column-live-loop-20261013/source/goalset_connection/` の candidate_goalset_v2、goalset_common_v4、resource_guard_v1 → `source/`
- `arc-column-candidate-query-20261013/source/` の candidate_query_v5、candidate_preservation_v1 → `source/`
- `arc-column-work-learning-20261013/source/column_work_harness_v3.py` → `source/column_work_harness_v3.py`
- `arc-current-family-source-20261013/接続/` の 列図式規則、図式観測、ARC3境界 → `source/`

旧ソースの絶対パスは書き換えていない。旧ディレクトリも作っていない。
例えば candidate_goalset_v2 は import 時に旧 COMMON パスを開き、candidate_query_v5 は
旧 contract_v1.json を開く。従って `source/` をそのまま import する起動手順は提供しない。
ファイル名・hash は同一性検証と証拠参照にだけ使用する。

## 実行済みの検査

```sh
cd arc-restart-baseline-20261016
ulimit -v 524288
PYTHONDONTWRITEBYTECODE=1 python restore_baseline.py
PYTHONDONTWRITEBYTECODE=1 python verify_baseline.py
```

復元元は隣の `arc-preservation-recovery-20261016`。別の位置にある場合は
`restore_baseline.py --recovery-root /absolute/recovery/path` を指定する。
同一ファイルが既にある場合は照合だけを行い、異なるファイルを上書きしない。
`restore_baseline.py` は allowlist で指定した archive member のみを取り出す。
`verify_baseline.py` は hash・AST 構文・JSON の識別子と台帳長のみを検査する。
HDS のデシリアライザは使わない。

結果は `restoration_receipt.json` と `verification.json`。
純粋な保存境界テストと小さい fixture 計測は `tests/` と `test_results/` に分離している。
テストの適用範囲・弱点の実測結果は同ディレクトリの報告を参照する。

```sh
PYTHONDONTWRITEBYTECODE=1 python -B tests/test_pure_save_boundaries.py --result-subdir review-run
```

38 ケースの assertion は成立した。そのうち 12 ケースは弱点を再現する検査であり、
保存経路の全面合格ではない。主な再現結果:

- 旧 harness は nonce ディレクトリの symlink を辿る。隔離 fixture 内でカテゴリ外への保存を再現
- full scan は行うが、要求外カテゴリの上限超過を拒否しない
- harness の保存後に再 guard がなく、保存中に増えたファイルをその保存呼出しでは検出しない
- disk 下限に prospective extra を含めない
- save/standard の try より前の期限切れは exceptions 台帳に記録されない
- standard の mkdir 失敗は save timer を有効なまま残す
- 保存完了後の compute 再開期限切れでは、ファイルはあり pending は既に消え、返却は例外になる

正常保存・重複名・短書込み・readback 不一致・fsync 失敗・同一性差・上限境界・
追加/resize/delete の再走査も検査した。内部保存失敗では pending と部分ファイルの保持を
確認した一方、外側の live failure loop が永続的にこれらを保存することは未検証。
この作業では弱点を修正していない。

対象の区別: 「保存後の guard がない」は `column_work_harness_v3.Run.save` の抽出試験結果。
`resource_guard_v1.save` は保存前後に guard があり、保存中の外部増加と symlink の追加を
保存後に拒否する試験が成立した。この2経路を同じものとして扱わない。
現行採用接続がどちらの guard/save を実際に束縛するかは、本基底では実行・認定していない。

大きいカテゴリ上限、RAM/disk、期限は明示した stat/fstat・資源・時計の test double を使用する。
実機 RAM 枯渇、非同期 SIGALRM、停電耐久性、race-free 性は証明しない。
48 ファイル・12,288 bytes の fixture で scan / 圧縮 / file fsync / directory fsync を別々に
計測した。3,520 回保存の速度や改善量へ外挿しない。

## 未充足の依存関係

`dependency_availability.json` は 14 archive のヘッダを対象に、36 依存参照の配置を調べた結果。
ヘッダに存在するだけの項目を、hash 検証済み・実行可能とは扱わない。

1. 次の正確な解析ファイルは、回収した 14 archive のヘッダに存在しない。
   - `arc-next-family-audit-20261013/goalset_preparation/goalset_preparation_preservation_analysis_v1.json`
   - 358,669 bytes、SHA-256 `a86fb6da4582d5e8db24032cef2fa8f1a661fe55ca48ca2e8643a9ef5faffd85`
   - 旧診断を全く同じ条件で再実行する際の blocker。代替内容を作っていない。
2. candidate-query の contract_v1.json は 4 archive のヘッダにあるが、本基底へは取り出していない。
   他の実行証跡、teacher pack、既往の保存観測なども同様。新しい release gate は作っていない。
3. 元の public-recording-v2.jsonl は 67,880,086 bytes。archive ヘッダにあるが、
   本ディレクトリの 32 MiB 上限を単体で超えるため取り出していない。
4. 後期 fresh ソース、fresh043 継続の正確な source/evidence は未回収。
   回収済み状態から同じ実行を続けられるとは主張しない。
5. SDK の利用可否、現在の公開環境接続、native 状態復元、既存の回帰は未試験。

## 次の最小工程

この作業では live launcher を作らない。まず純粋テストが示す保存失敗・期限切れ・
symlink 境界の欠落を、凍結 HDS の外側の最小接続変更として個別に扱う。
原本を変更せず previous/current/delta と失敗証拠保存を比較し、修正の採否を決める。

最優先の最小変更契約は「採用接続の実際の save/guard 束縛を静的に固定し、その外側で
保存開始前の期限切れ・mkdir 失敗・保存後 compute 再開失敗を捕捉する」こと。
新しい接続側ラッパーだけを対象とし、原本/HDS を変えず、primary 例外、pending、
部分ファイル、保存済み FileRef を消さない。期限・名前・symlink とカテゴリ境界は緩めない。
採用 gate は同一 inert packet で previous/current を比較し、通常成功の bytes/hash・
呼出し順・全走査が同じで、上の3失敗点すべてに追跡可能な証拠と timer 停止があること。
保存後 guard の追加は実際の採用経路に欠落がある場合にだけ行い、既存 wrapper の
二重化や「resource_guard_v1.save にも欠落がある」という誤った修正をしない。

その後の最小 live 接続工程は、独立した新しい作業として、対応パスと入力 closure を閉じた
読取り専用の preflight を作り、明示された有限 release gate の下で公開応答 1 件を全相保存・
readback すること。native 復元や照会へ進む前に、必要 FileRef、保存失敗時の挙動、現在の
公開環境アクセスを検証する。欠けた旧解析を再現したことにはせず、新しい工程の証拠を分ける。
候補削減、観測省略、HOLD 緩和、replay lookup は導入しない。

## 資源・不変条件

- 本ディレクトリ全体 32 MiB 以下
- 実行プロセス AS 512 MiB 以下
- 空きディスク 1 GiB 以上
- archive と回収済み原本は変更しない
- AGENTS、権限、制御/現在状態、HDS 中核は変更しない
- ソース側の full-scope scan は保持。cache や高速化は未導入
- Git 書込みなし。main 公開は別の単独担当工程

本ディレクトリは証拠と再現検査用であり、現在状態・権限・採用 runtime の変更ではない。
