ARC3 最初の fresh レベル成功チェックポイント
2026年10月13日 UTC

1 結論
固定した HDS v0.4.2 を用い、fresh instance の同一環境で観測、全候補の照会、採否、Action、再観測を繰り返し、公開 completed levels の 0 から 1 への遷移を確認した。9 Actions、126 Queries、Teach 0。独立監査は PASS。最初の成功1レベルであり、全183レベルに対して約0.55%。25ゲーム走破、対象ゲームの全8レベル完了、未見問題への転用を示す結果ではない。

2 固定した基底と学習
main基底は 9ce1830494bb80f5d820fbad61ca9096954a04c6。HDS中核 v0.4.2 は変更していない。事前78経験に修復13、準備14、保存24の教師経験を加えた129経験を保持した状態を使用した。これらの教師原票と学習閉包は既に別送したCP3に記録済みで、本書では巨大な既送録画を重複収録しない。実運転中の追加 Teach は0で、今回の生の経験は新しい学習済み支持として昇格させていない。
対象は公開教師と同じ初期盤面。別fresh instanceでの完全な9手再現は、このチェックポイント時点では未実施。初回成功と独立読取監査を、別実行での再現成功と読み替えない。

3 確認できた差分
先行パイロット 502f9dd64c29158c6189c4efa50c107d は fresh 1 Action、13 Queries、Teach 0 で準備操作が成立し、公開レベル数は0のまま。独立監査 PASS。
本ループ d7bbc7465f691c7bb7bb6e5a76089762 は、そこから引き継いだ学習機状態を新しい環境に接続して9手を実行し、公開レベル数が1になった。全150応答相（最終提出118相）を保存。11個の正常状態における学習知識と履歴は保持され、照会カウンタだけが378から504へ増加した。これは同一条件の統制比較による汎化性能改善率ではない。

4 各手の判断と原票
候補の固定生成順で支持された候補を選ぶ方針は呼出側の方針であり、学習済み選択方策だとは主張しない。毎手、新しい公開観測を投影し直し、当該状態へのHDS実照会と適用前提で採否している。全候補、非採用理由、支持索引、照会の生入出力、前後公開観測、日本語Runtime Memoryを収録した。以下の原票名はループのnonceディレクトリ内を指す。

手 1（step_00）: 在庫記号を選択。Action 6 {"x": 20, "y": 59}。Query 13、応答 1 相。採用候補 0。前提 {"実クリック在庫記号が未充足要求に適合": true}。未実行候補 1,2,3,4。
  支持根拠: 作用対応,目標効果 の当該状態への実照会。保存条件の由来: 保存対象なし。
  原票: step_00_9d04da30b9f448c48721cbca96e77fcb_dossier.json、同接頭辞 support-index.json / full-candidates.typed.json.xz / Japanese_RuntimeMemory.typed.json.xz、transport/9d04da30b9f448c48721cbca96e77fcb.before.json と .response.json。

手 2（step_01）: 選択記号を空欄へ割当。Action 6 {"x": 29, "y": 30}。Query 17、応答 7 相。採用候補 5。前提 {"実対象への選択記号適合": true}。未実行候補 0,1,2,3,4,6,7,8。
  支持根拠: 作用対応,目標効果 の当該状態への実照会。保存条件の由来: 保存対象なし。
  原票: step_01_f6cefea2cc184382828230b0a05683a4_dossier.json、同接頭辞 support-index.json / full-candidates.typed.json.xz / Japanese_RuntimeMemory.typed.json.xz、transport/f6cefea2cc184382828230b0a05683a4.before.json と .response.json。

手 3（step_02）: 在庫記号を選択。Action 6 {"x": 28, "y": 59}。Query 14、応答 1 相。採用候補 0。前提 {"実クリック在庫記号が未充足要求に適合": true}。未実行候補 1,2,3。
  支持根拠: 作用対応,目標効果,保存条件 の当該状態への実照会。保存条件の由来: HDS実学習。
  原票: step_02_678e4931e3064501806645bdd79c049c_dossier.json、同接頭辞 support-index.json / full-candidates.typed.json.xz / Japanese_RuntimeMemory.typed.json.xz、transport/678e4931e3064501806645bdd79c049c.before.json と .response.json。

手 4（step_03）: 選択記号を空欄へ割当。Action 6 {"x": 41, "y": 30}。Query 20、応答 7 相。採用候補 6。前提 {"実対象への選択記号適合": true}。未実行候補 0,1,2,3,4,5,7。
  支持根拠: 作用対応,目標効果,保存条件 の当該状態への実照会。保存条件の由来: HDS実学習。
  原票: step_03_a3eab4529e8f417cb99d7eaa0b119fee_dossier.json、同接頭辞 support-index.json / full-candidates.typed.json.xz / Japanese_RuntimeMemory.typed.json.xz、transport/a3eab4529e8f417cb99d7eaa0b119fee.before.json と .response.json。

手 5（step_04）: 在庫記号を選択。Action 6 {"x": 36, "y": 59}。Query 11、応答 1 相。採用候補 0。前提 {"実クリック在庫記号が未充足要求に適合": true}。未実行候補 1,2。
  支持根拠: 作用対応,目標効果,保存条件 の当該状態への実照会。保存条件の由来: HDS実学習。
  原票: step_04_a654c8454c784caf983cb517a3c50082_dossier.json、同接頭辞 support-index.json / full-candidates.typed.json.xz / Japanese_RuntimeMemory.typed.json.xz、transport/a654c8454c784caf983cb517a3c50082.before.json と .response.json。

手 6（step_05）: 選択記号を空欄へ割当。Action 6 {"x": 23, "y": 30}。Query 19、応答 7 相。採用候補 2。前提 {"実対象への選択記号適合": true}。未実行候補 0,1,3,4,5,6。
  支持根拠: 作用対応,目標効果,保存条件 の当該状態への実照会。保存条件の由来: HDS実学習。
  原票: step_05_2ce50cbd27c042239f69f6238cc968df_dossier.json、同接頭辞 support-index.json / full-candidates.typed.json.xz / Japanese_RuntimeMemory.typed.json.xz、transport/2ce50cbd27c042239f69f6238cc968df.before.json と .response.json。

手 7（step_06）: 在庫記号を選択。Action 6 {"x": 44, "y": 59}。Query 8、応答 1 相。採用候補 0。前提 {"実クリック在庫記号が未充足要求に適合": true}。未実行候補 1。
  支持根拠: 作用対応,目標効果,保存条件 の当該状態への実照会。保存条件の由来: HDS実学習。
  原票: step_06_640a8f126e3843698b809be89406ce63_dossier.json、同接頭辞 support-index.json / full-candidates.typed.json.xz / Japanese_RuntimeMemory.typed.json.xz、transport/640a8f126e3843698b809be89406ce63.before.json と .response.json。

手 8（step_07）: 選択記号を空欄へ割当。Action 6 {"x": 35, "y": 30}。Query 18、応答 7 相。採用候補 3。前提 {"実対象への選択記号適合": true}。未実行候補 0,1,2,4,5。
  支持根拠: 作用対応,目標効果,保存条件 の当該状態への実照会。保存条件の由来: HDS実学習。
  原票: step_07_ee4f2d11166d4b719e71ff6728bcfc84_dossier.json、同接頭辞 support-index.json / full-candidates.typed.json.xz / Japanese_RuntimeMemory.typed.json.xz、transport/ee4f2d11166d4b719e71ff6728bcfc84.before.json と .response.json。

手 9（step_08）: 完成列提出。Action 5 {}。Query 6、応答 118 相。採用候補 0。前提 {"終端条件に応じた列が一致": true}。未実行候補 なし。
  支持根拠: 作用対応,目標効果 の当該状態への実照会。保存条件の由来: 受理による旧問題終端のため対象外。
  原票: step_08_e0440a5fbd9345aabb609eafe68bf290_dossier.json、同接頭辞 support-index.json / full-candidates.typed.json.xz / Japanese_RuntimeMemory.typed.json.xz、transport/e0440a5fbd9345aabb609eafe68bf290.before.json と .response.json。

5 終端と UNKNOWN の扱い
completion.current_public は最後のAction直前の参照であり、最終公開応答ではない。CONTINUEのときだけ current_public が更新され、成功終了は更新より前に保存されるためである。最終応答は completion.step.public_response、具体的には transport/e0440a5fbd9345aabb609eafe68bf290.response.json（673181 bytes、SHA256 241dca1bb994d2f30aa2363d4248cd0cf7986df0074ed6eae24d03f4767475b8）。最終応答欠落ではない。
提出は、現在の列が終端条件に一致するとの支持と採否に基づく。提出後は旧問題の意味範囲が終了するため、旧範囲の UNKNOWN を保持し、通常の保存条件を成功へ改変しない。レベル成功の根拠は、採用済み提出の公開応答における completed levels の増加である。終端演出中の知覚例外・不適用も原票に残している。hidden state と reward は未観測。そこから隠れた因果や報酬を推測していない。

6 失敗と限界
先行起動 2a1f6f20880913b61706edfff74d3a84 は環境make前に ModuleNotFoundError で失敗した。モジュール名はUNKNOWNのまま扱い、当時のowner 2505と失敗証拠を保持した。Action再試行による回復ではなく、後続の別許可起動で既存の公式接続用venvを使った。元の失敗原票、actual tool receipts、監査の途中失敗、純粋fixtureの旧失敗とソース版を含めた。opaque SDK出力の本文とゲーム実装は収録・読解していない。
成功軌跡の新しい学習規則化、別盤面・別ゲーム転用、完全fresh再現、残り182レベルの成功はいずれも未確認。現在の新ループ版の実装・試験はこのチェックポイントに含めない。

7 検証と再読方法
source_manifest.json の各相対path、bytes、SHA256で原票を対応付ける。元JSON内の絶対pathは /workspace/scratch/a94ff513b3af/ をアーカイブ展開先に置き換えて参照できる。各手の採用根拠と全候補.json は全候補の検査と生原票参照を一覧化したもの。契約、release、core/source pins、独立監査ソースと結果を同梱した。
証拠の再読はSDKやHDSやActionを呼ばずに行える。本アーカイブは読取監査用の閉じた証拠集合であり、ゲーム実装、SDK実行環境と以前の教師全記録は別管理。再実行にはそれらのpin一致および新しい実行許可が必要で、古いreleaseを再利用しない。外部参照と除外理由は source_manifest.json に明記した。

8 資源上限
追加保存は既存ループscope512 MiB（source16、evidence464、failure32）内のcheckpoint用32 MiB以下。新しい外部quotaは増やさない。global disk future2004 MiBとfloor1024 MiB、RAM reserved5632 MiBとfloor2048 MiBを前提とし、包装workerのASを512 MiBに制限した。アーカイブ生成、SHA計算、読戻しは64 KiB単位で流し、全展開コピーは作らない。
検証結果と完成アーカイブのbytes/SHA256は archive_validation.json を参照。gzip全量EOF/CRC、tar全member、manifestとの一致、各memberと元ファイルの全byte再読を検査する。これは新たなゲーム再実行ではない。
