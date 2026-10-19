# 固定観測条件下の端点値同値を学習したnative限定実験

## 目的

公開された過去の観測における、対象の前値・器具値と、同一問題内で定義した端点の対象値との対応を、固定HDS v0.4.2の通常教示で学習できるか確認する。ゲームActionや実行経路の採用はこの単位の対象にしない。

## 観測

- 1回の許可済みnative実行で、30 Query → 15 Teach → 30 Queryの75呼出が完了。入力・出力・呼出後入力の225記録と、18全状態snapshot索引の計243frameを保存した。
- 経験は189→204、原理recordは19→27。新規は4本の有向同値関係lineageで、各2版、計8版である。内側・外側の2関係familyについて順方向と逆方向がある。
- nativeで適応したのは教師4・7・9・11。残り11件の「接続途上」も、保持・評価された結果として残す。15件全部が新しい原理適応だったとはしない。
- 新しい順方向照会11件は、beforeでは状態「出力」、予測なし、学習状態「適用外」。afterでは全件が条件値と等しい単一の端点値を返した。うち7件はその境界の教師で観測済みの値、4件は教師にない色1/2である。
- 逆方向の2原理は保存状態で確認した。この75件のplanには逆方向の独立照会testは含めていない。

## 原因と変更

以前のliteral13/14候補や、連続的な対象保存・MASK作用そのものという広い解釈は、観測だけでは確定できなかった。初期selectorのNONE、途中geometryのHOLD、余分なendpoint templateによる失敗を残し、限定した端点観測契約へ段階的に修正した。

最終revision03は「BEFORE参照が保たれる連続prefix末尾2相（切替がない場合はpacket末尾）」を用いる新しい固定観測手続である。今回phase15で参照が再結合するのはcase4/5である。予測した色へ合わせたり、以前の都合のよいframeへfallbackしたりしない。幾何、mask内外、対象role、器具role、問題の結合条件は依然としてpriorである。これらをHDSが学習したとは扱わない。

その明示された条件下で、HDSが通常教示から得たものは、対応付けられたscalar値の同値関係である。4本のlineageを、独立に獲得した4種類のAction原理とは数えない。

## previous / current / delta

previous: main 2ca6531908551755988ade040840362684c96b14。直前の189経験・19原理版のdescendant、および既存の教師対照・全候補診断を参照する。

current: 閉鎖済みの設計、教師計測3段階、独立教師review、静的容量証明、native実行、呼出側と実行結果の独立reviewを保存する。6root、399元file、160,290,700 bytesの追加allowlistを固定した。各rootの過去manifestは時系列の部分freezeとしてそのまま保持する。

delta: 15経験、8原理版が増え、限定した順方向11照会が予測なしから指定同値値へ変化した。環境Action、freshクリア数、フルゲーム成功、速度改善は増分として主張しない。

作成者freezeの「独立review待ち」という文言も変更せず保持する。後続のfinal_execution_auditのBOUNDED NATIVE IDENTITY EVIDENCE PASSが、その後に成立した検証結果である。

## regressionと証拠

- 既存189経験、19原理record、過去の台帳・原理履歴・状態履歴のprefixは全snapshotで不変。既存181個の前実験fileと64個の固定入力/source pinも再確認されている。
- 19件の既存smokeは、状態・予測・競合・追加観測要求・識別不能・係争・HOLD理由・学習状態などの対象投影が同じ。全raw replyは全19件で異なり、新しい全体原理summary、state/counter/traceの差を保持する。全既存成功の完全回帰ではない。
- Queryだけの前後batchは対応counterを各30増加。6698→6728→6758。全native delta、全原理版、支持・反証、追加台帳を保存する。
- 最終outsideの支持は経験190/192/193/195/196、insideは191/194/198/200。後続の同じ対応の観測は経験台帳に残るが、対応表が変わらないと原理版の支持tupleは更新されない。15新経験すべてが最終active原理の支持列へ入ったとはしない。
- 第7保存のallowlist不足、修正時assertion失敗、reviewerのtuple/list比較失敗も、修正前sourceとstdout/stderr/exitstatusを含めて残す。
- 初期operation-contractのinline KeyErrorについては、完全な元standalone sourceが保存されていない。この欠落はinspection_failure_history.txtに開示され、後の再構成を元sourceと称していない。

## 資源

native実測wallは19.550615941秒、peak RSSは86,976KiB。512MiB AS、CPU上限120秒を設けたが、実CPU秒は個別には測定されていない。

全状態は5,558,643→6,116,344 bytes、増分557,701。静的上界7,221,324 bytesおよび8MiB slot以内。最大reply43,111 bytesは証明上界60,103 bytes、64KiB gate以内。evidence有効prefix3,121,785 bytesは上界6,519,712 bytes以内。

全19single-use state slot、未使用失敗slot、evidence/emergency予約を、現在残る実file bytesのまま可逆圧縮して保存する。168MiBは論理予約量であり、native保存は一部fileをtruncateする。実file総量が小さいことをslot再利用許可や物理的なENOSPC耐性の証明にはしない。

## limitations

- 教師15行は5つの情報を持つ歴史Action、2 recordingからまとめた相関した観測。新しい環境観測は0件。6 Action・600cell・112phaseを保持し、150曖昧cellはlabelを付けない。
- 未観測色の照会は、宣言した観測境界内でnative同値関係を代数的に適用した結果。新環境・別gameへの転用、連続する対象identity、MASKの因果、唯一の作用機構、幾何・回転・合成の学習、将来の保存は示していない。
- phase15の目標再結合は別の条件であり、将来実行では現在目標を取り直す必要がある。
- HDS本体・AGENTS・権限順序・現在状態は変更しない。自己判断でruntimeへ採用しない。経験204をクリア204レベルとは数えない。別の既存検証で確認された基準はfresh成功1/183、フルゲームWIN未達のままである。この399-file内容監査がfresh能力を再測定したものではない。
- この追加payloadの内容検査と、repositoryの過去HDS正本文書の公開範囲確認は別件である。公開範囲が未解決の間、Gitへの追加は停止する。
