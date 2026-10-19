# 歴史教師6件による限定 native 学習・全状態保存

## 目的
既存公開記録から固定した教師を現行 HDS の子孫状態へ実際に投入した結果と、先行失敗・容量証明・独立監査を保存する。成立した保存・限定学習の証拠として扱い、runtime の採用や制御上の自動遷移は行わない。

## 観測
最終実行は 19 Query → 6 処理する → 19 Query の計44件を entered/returned/fully-persisted まで完了。132件の入力・出力・処理後入力記録と9件の状態索引、計141 framed records、および9個の完全 native 状態を保存した。独立監査は BOUNDED_NATIVE_EVIDENCE_PASS。先行2試行は bootstrap で停止し、それぞれ Query/処理/保存は0件。診断2回も Query/処理/保存は0件で、最初の HOLD と修正後 BINDING_PASS_NO_CALLS を両方残す。

## 原因
最初の停止は「unexpected native module global」で、拒否された属性名自体は原記録にない。interpreter の直接子 module を厳密 binding 検査が拒否したという説明は静的・合成試験による診断であり、その属性を初回native実行が直接記録したとは扱わない。2回目の pinned Enum._generate_next_value_ の拒否は直接診断された。修正は同一性の検査に限定された。最終的には、固定幾何・末端公開進捗という明記済みの境界内で、歴史教師の4種類の条件値から deterministic correspondence が native 学習された。画像認識、mask、role、条件射影自体を今回学習したわけではない。

## 変更
本commitは証拠専用。3試行と bootstrap 診断の凍結181ファイル、その freeze_manifest、閉鎖済み容量・呼出側・実行結果レビュー76ファイルを、全予約領域のゼロ末尾を含め無損失圧縮して保存する。元ファイル258件、266,290,089 bytes。payload_manifest と archive_verification が全メンバーを列挙する。既存入力4pack・基底状態・固定中核12ファイルは既に main に保存されており、origin_verification に archive/member と hash を記載して重複収録を避けた。今回の normal_state は実測 roundtrip checkpoint として含む。

## previous
開始main: 9144b553c20db3bee4a4b1065abc316dd352f90a。native状態は183経験・16原理レコード、照会counter6660、完全状態5,355,957 bytes。対応する6件の学習前照会はすべて「状態=出力、予測なし」であり、native HOLD ではない。

## current
189経験・19原理レコード、照会counter6698、完全状態5,558,643 bytes。対応する6件の学習後予測は false,false,false,false,true,true。6教師の学習成立状態は順に 接続途上,接続途上,成立確認,成立確認,成立確認,接続途上。

## delta
実 Query 38件、実処理6件、経験+6、状態+202,686 bytes。一つの新しい原理系統に version1/2/3 が加わったのであり、独立な汎用法則が3個増えたという意味ではない。最終versionの支持は経験184–188。6番目の重複教師189は保存・評価され、candidateの支持には含まれるが、対応表が同じなので新versionも既存versionの支持更新も生じなかった。false の結果4件は負例であり、原理の反証台帳への自動追加を意味しない。

## regression
旧台帳・原理履歴・状態履歴の全prefixは不変。両19 Query区間で意味状態は対応counter以外不変。既存13件の control/boundary smoke で状態・予測・競合・追加観測要求・識別不能・係争中原理・断定保留理由・学習成立状態の関連射影が一致した。全raw replyは状態version・参照ID・active原理summaryの追加などにより異なり、その差も保存した。既存成功全体の回帰を完了したとの主張はしない。

## 資源と保存履歴
実行wall約10.003秒、peak RSS81,168 KiB。AS512 MiB、CPU上限120秒、wall上限240秒。実CPU秒は別途測定されていない。最大input505 bytes、最大reply35,083 bytes、framed evidence有効部1,586,947 bytes。完全状態は分析上限8,042,933 bytesと8 MiB slot以内。3試行それぞれの92 MiB予約を含め全47予約ファイルの全bytesを保持する。成功時の状態書込みが予約ファイルをtruncateしたため、実ファイル合計と予約論理量は異なる。resource_validation、独立監査、最終freezeの合計値は各測定時刻の追加metadata量が異なり、相互に上書きしない。

Producerの RESULT.md と freeze_manifest の「独立監査待ち」は当時の凍結原文を維持する。後続の arc-teach-launch-review-20261019/final_execution_audit が完了判定である。初回独立監査の empty tuple/list 誤認による assertion failure と修正後PASSも両方収録した。準備時の一部初期sourceがin-place更新され、厳密な修正前原本が欠ける点、freeze script初回syntax失敗は断片再構成しかない点を明記した原記録を保持する。完全な失敗履歴が復元できたとは扱わない。

## limitations
教師6件はこの子孫状態にとって新規だが、独立に新しく観測したデータは0件。4種類の学習条件そのものを再照会した限定結果であり、held-out汎化・必要十分条件・連続保存・幾何の正しさ・fresh instance転用・ゲーム間転用・live Action安全性を証明しない。77 phase の解釈は未確定で、正例末端の参照binding変化も残る。SDK/Actionは0件。経験189はクリア数ではない。現存する認証fresh成功1/183（約0.55%）とfull-game WIN未成立は変わらない。

native保存のtruncate/ENOSPC/物理割当喪失、kernel停止等を万能に保存できる保証はない。UNKNOWN frontier から自動再開してよいとはしない。HDS・AGENTS・権限文書・現在状態・既存mainの内容は変更しない。以前の復旧coverageは13/14原archiveの完全保存と公式接続の除外明記派生物であり、fresh043や歴史分析358,669 bytes等の未復旧証拠は未復旧のまま。「全作業保存済み」とはしない。

## 読み方
archive内の MANIFEST.json と外部 archive_verification.json で全メンバーのhashを確認し、freeze_manifest → raw reserve/full state → result_audit/native_full_delta → final_execution_audit の順に照合する。予約領域の有効prefixとframe位置は reserve_prefix_index.json を参照する。Pythonは保存された実装・テストの証拠であり、このcommitを読むために実行する必要はない。
