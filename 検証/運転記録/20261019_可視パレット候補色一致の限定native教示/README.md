# 可視パレット・器具の候補色一致を学習した限定native実験

## 目的
公開された過去の観測から作った、選択された可視パレット色と観測後の可視器具色についての候補色一致関係を、固定HDS v0.4.2の通常教示で学習できるか確かめる。対象は既存の可視配置と固定されたrole認識の範囲である。

## 観測
- 一回の許可済み実行で32 Query → 6 Teach → 32 Query、計70呼出が完了した。210件の入出力・呼出後入力記録と9件の全状態snapshot索引、計219 frameを保持する。
- 経験204→210、原理record27→29、照会および学習判定counter6758→6822。新しい2原理は順方向・逆方向の有向Boolean同値関係で、各version1。両方の保存された支持経験は205–207である。
- 教師3で一度の適応が起きた。他の5教師の「接続途上」と、経験208–210が保持・評価されても支持リストや版を更新しなかった事実を残す。
- 新しい順方向照会2件はbeforeで状態「出力」・学習状態「適用外」・予測なし。afterでそれぞれtrue/falseの条件値と等しい一個のBoolean予測を返した。beforeをHOLDと読み替えない。両Boolean値は既存教師に現れており、未知値の汎化試験ではない。逆方向原理の存在は状態で確認したが、逆方向Queryはこの実験で別途試していない。
- 既存30照会は関連する出力投影が一致した。全30件のraw replyは異なり、全出力一致とはしない。対象投影は状態、予測、競合、追加観測要求、識別不能、係争中原理、断定保留理由、学習成立状態である。
- 元の204経験・27原理と他の台帳・状態履歴のprefixを保持した。各Query-only区間では対になったcounterだけが正確に32増えた。全native deltaを別途保持する。

## 原因と変更
本体や学習原理を変更せず、歴史的な可視パレット観測を、recording×Booleanの6つの相関した教師群へ整理した。101件の歴史的palette clickから584件の候補比較を得ており、483件の負の候補比較と3件の既に一致していたclickも含む。この件数を独立な環境試行数とはしない。新しい環境観測は0である。

固定されたpalette/tool認識、可視配置、click offset、Action command、候補色解釈、教師の群分けと適用境界を前提として使う。学習したのは、そのqualified namespace内のBoolean対応である。目標色の決定や座標選択を学習したことにはならない。

## previous / current / delta
- 保存先の開始main: 2ca6531908551755988ade040840362684c96b14。別の読み取り確認でも同じtreeと保護文書の全bytes一致を確認した。
- native previous: 204経験、27原理record、counter6758。前回identity状態をhash固定して使用した。
- native current: 210経験、29原理record、counter6822。
- delta: 6経験、2有向Boolean原理、64 Query。新規実Action、SDK呼出、fresh成功、ゲームclearの追加はない。
- ゲーム能力の基準は外部の以前の確認に依存する。本checkpointはfresh成功を再計測していない。

## regression と失敗保持
以前の181件の教師実験freeze、105件のidentity freezeと、今回114件のnative freezeを独立監査で再照合した。元の失敗を含めて変更はなかった。manifest自身とclosure02の終了ログはfreezeの自己参照外として別途収録する。

静的boundのpre_fix01/bound01と修正版bound02を残す。COPY用generatorの一括range置換が、lineage数だけでなく経験の観測項目数を4から2へ誤って減らした。訂正したstate upperは6,628,545→6,638,745 bytesである。先行identity/goal6の固定された証明にはこの欠陥はなかった。元の証明や失敗を消さず、後続の訂正を区別する。

execution01はmanifestの相対root解釈でallocation/native import前に停止した。明示的root confinementを直したexecution02だけが今回のnative実行である。finalize01は報告用の繰返し読取りで中断されexit130となり、finalize02はnative再実行を伴わず訂正した。元のsource/log/statusを保持する。独立レビューの初回test adaptation失敗、修正版、freeze未到着のaudit precheck失敗と最終PASSも残す。producerのREVIEW_PENDING表記は元のbytesのまま保存し、後続reviewerのPASSで時系列を説明する。

## 資源
実測最大stateは6,324,220 bytes、増分207,876 bytes。最大reply47,312 bytesは修正版proof62,525 bytesと64KiB cap未満。evidenceの有効prefixは3,289,992 bytesで、proof5,956,320 bytes内に収まった。native最大RSS93,088 KiB、supervisor wall12.2046秒。96MiB単位上限と576MiB保持集合の範囲内を監査した。

予約領域の実在bytesとzero tailを損失なく保持する。native保存が予約fileをtruncateする事実を隠さず、論理上の書込範囲や実測値を物理ディスクのENOSPC耐性・永続化保証と呼ばない。

## 保存範囲
原payloadは358 files / 95,287,868 bytes。native、pilot、bound review、caller reviewの4閉鎖rootと、測定producerが明示した68ファイルおよび6件のallowlist実行記録だけを収録する。測定parentを再帰取得しない。

初期のmixed-cohort ancestor JSONにはTURN/MASK行も含まれるが、COPY抽出の正確な由来を保つために元bytesのまま残す。これはその別操作を今回nativeで学習・採用したことを意味しない。generic namespaceのHOLD、qualified proposalの旧版と最終copy6_qualified_v2、およびreview run01/02/03/05を保持する。独立したtarget-observer、現在のTURN plan、関連しないMASK出力とその失敗は本checkpointの閉鎖範囲外であり、削除せず別の保全対象とする。

## limitations
- この結果はhistorical qualified palette観測のBoolean同値であり、role発見、geometry学習、目標参照の正しさ、因果の一意性、freshな作用の十分条件、安全なAction採用、一般ゲーム能力、全過去成功の保持を証明しない。
- 30照会はsmoke regressionであり、全過去条件の網羅試験ではない。
- full public recording、固定core、先行状態と証明は既存のhash参照に従う。公開済み・私的保存済みの大きな入力archiveを重複収録しない。参照だけでは単独再現可能とは主張しない。
- 現在のfresh観測で器具色が唯一の不足色と既に一致した場合、目標駆動のpalette選択はHOLDを維持する。新たなActionは別の現在候補bindingと許可を要する。
- 内容監査とhistorical HDS正本文書の公開範囲確認は別件である。Ownerの具体的確認が未回答の間、Gitへの追加を停止する。私的なHDS disclosure調査rootとraw tool receiptsは収録対象から除く。
