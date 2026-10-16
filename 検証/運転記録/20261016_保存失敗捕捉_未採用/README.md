# 保存失敗捕捉の隔離試作 2026-10-16

## 結論

**NOT_ADOPTED。現在の運転接続へは採用していない。**

凍結 HDS の外側に小さい保存呼出しアダプターを作成し、純粋 fixture の
63 ケースが成立した。内訳は従来の境界検査38件と新規捕捉検査25件。
従来検査には弱点を再現する12件が含まれるため、63件を全保存経路の安全認定や
学習能力・成功レベル数の改善に読み替えない。

HDS import、native 復元、Query、Teach、SDK、Action、live 起動、Git 操作は0件。
中核、権限、現在状態、回収原本、既存 archive は変更していない。

## 固定した歴史的な呼出し束縛

回収済み saved59/saved118 の wrapper は、旧 column_work_harness の Run.save と
Run.standard を AST で組み立てた BaseRun から継承する。
その guard は組立先 harness の guard を経由して resource_guard.guard を呼ぶ。
resource_guard.save を呼ぶ経路ではない。

resource_guard.save 自体には保存前後の full guard がある。
継承された歴史的な Run.save には保存前の full guard が1回ある。
この違いを保った。postguard の追加・二重化、上限の変更、走査省略は行っていない。
根拠のファイル、行、hash、archived pins は binding_proof.json と
evidence/input_manifest.json にある。

後期 fresh043 のソース・証拠が未回収なので、この歴史的束縛を現在の採用接続とは
認定できない。これは live 再開の blocker であり、本試作はそれを解消したものではない。
回収状態の183は経験数、16は原理数、6647は対になる識別子counter。
183レベル成功という意味ではない。

## 変更と検査

新しい source/save_capture_not_adopted.py だけで呼出し側を追加した。
原メソッド・原モジュールの monkey-patch はしない。

- 通常成功は原メソッドに委譲。圧縮bytes/hash、型と順序、full scan、open/fsync/clockの順序が一致
- try前の保存期限切れと standard のmkdir失敗を捕捉
- 保存完了後のcompute再開失敗でも、既知の自作メソッドcodeとreceiverに一致するframeだけから完成済みFileRefを保持
- 以前のpending、新しいpending、試行内容は参照のまま保持。任意のlocalsやnative/SDK/evaluator frameを読まない
- 部分ファイルを上書き・削除しない。既存出力はnonblocking/no-follow・regular-file検査・32MiB読取上限の下で観測
- 診断は既存failure120秒の総予算を消費し、延長・リセットしない。終了時にtimerを停止し、元の例外を再送出
- 旧証拠との名前衝突、capture割当・append失敗、診断容量不足、failure期限切れ、timer停止失敗、診断部分書込みを区別して保存

失敗sinkのfixtureは、元のincremental failure4MiBとresource guard全上限を通し、
元のresource writerの前後full guardとexclusive createを保つ。任意のsinkを認定しない。
診断保存自体が失敗したときは「保存済み」と扱わない。残ったbytesは削除しない。

最初のrun_01は、新規テストfixture名の誤りで15件がsetupエラーとなった。
そのrunner、adapter、JSON、logを残した。後の成功で上書きしていない。
独立レビューで見つかった「FIFO等の無期限読取り」「捕捉処理が元例外を隠す」も
修正前の証拠とともに保持し、修正後の再検査を記録した。

## 再検査

同梱した自作ソースの読取りと、stdlibだけのfixtureを使う。HDSソースは同梱しない。
新しい結果名で実行する。既存の結果ディレクトリは上書きしない。

    ulimit -v 524288
    PYTHONDONTWRITEBYTECODE=1 python -B tests/test_capture.py --run independent_recheck

最新の確定結果は evidence/run_06_defaults/results.json と同test.log。
同ディレクトリに実行時のrunnerとadapterもある。

## 制限

- whole work 16MiB、AS512MiB、disk free1GiB。通常保存の上限・quota意味は変更しない
- native codec、実HDS保存、現在のlive接続、非同期signal、停電耐久性は未検査
- timer/資源境界には明示したtest doubleを使用。大きな実ファイルを作っていない
- capture予算・容量・メモリ・I/Oが足りなければ永続診断を保証しない。元例外の保持が優先
- timer停止そのものの失敗も報告する。停止できたと偽らない
- 診断を出す間はfailure timerが動作中。最終停止はunwind後の検査記録で確認する
- このアダプターは既存outerのHOLD/latchを置換しない。nativeの自動再試行はしない
- 残る旧弱点を修正済みとはしない。速度・能力改善を主張しない

目的・観測・原因・変更・previous/current/delta・regression・limitationsの一覧は
final_report.json に記録した。
