# C2-078 視覚solverとHDSの公開一手接続pilot

## 目的と現在位置

V6の目的は公式スコア改善とHDS学習の実証である。C1-024で確認した視覚推論・Python計画の経路へ、実際の公開作用応答によるHDS更新と事前予測を接続する。shadow接続・事前記憶読込・Notebook完走だけを目的達成にしない。

off-r2とshadow-R3のprivate GPU version1は両方COMPLETE。公開3ゲーム・各80Actionでoff-r2はRHAE8.333333333/4level、shadow-R3は5.952380952/3level。R3のHDS238更新・238照会・prior15更新は成功、エラー0。全照会はnative HOLDでモデルへ情報を渡していない。R2/R3のsourceは異なるので対応score差・学習効果を主張しない。次はC2-081のモデル候補照会をCPU準備し、C2-083で具体的な局所応答を学べるか診断する。公式Competition Rerunは未実行、既存の公式23.86版と共有runtimeは変更していない。

## 固定する比較

- 起点は保存済みv5 Notebook（SHA-256 `5763f69d0794d7161dbe81a967edd2c10a6810c92ed1a28208bd47222fd5dfbc`）。視覚モデル・system prompt・Python計画・memory offを保持し、共通の実験変更として両条件に`LOCAL_ANALYZER_SEED=0`を明示する。元版の既定値−1を固定seedの証拠にしない。
- 公開sourceは新準備先の同一版を両条件で使用。solver/ToolAgent/Python sandboxはv5 patch postimage一致、framework/run.pyには来歴差が残る。過去23.86のbit単位再現は主張せず、新controlを比較基準にする。
- off/controlとshadowで同じ公開3ゲーム、model seed0、80Action/game・1200秒/game、GPU有効・Internet無効のprivate通常Runを使用する。元のGameAPIはenvironment seedを明示していないため、0を指定したとは扱わない。SDK既定条件と、実際の開始board/state等を両armの出力で照合し、不一致なら対応比較を不合格とする。SDK・モデル・token/時間予算も照合する。GPUの完全決定性は仮定せず、行動へのHDS影響を試す段階では同版反復も行う。
- HDS budgetは1ゲームにつきupdate80、query80、累積HDS処理120秒。実行中の一呼出しは中断できず、超過し得ることを記録する。予算やHDSエラーで視覚solverを停止しない。
- 本候補はoffline pilot専用で、Competition Rerun分岐を拒否する。公式版へ昇格するには後段の全体比較と別の構築・検査が必要。

## 一手の因果境界

`_HarnessGameSession._execute_action`で、モデルが既に選んだ合法Actionについて、**実行前**の公開grid/state/levels_completed/available_actionsだけをHDSへ照会する。その後、元のActionを一回実行し、**その一手直後**の公開応答をHDSへ教示する。複数手batchの合成結果を一手の結果として使わない。RESET・automatic resetを通常作用の教師から除き、GAME_OVERの応答を再開画面で上書きしない。

HDSへ渡すのは公開画面から機械的に測れる条件・作用・応答区分だけ。modelの仮説、payloadの計算済みscore/reward、game/level ID、hidden/evaluator情報を条件へ渡さない。GAME_OVERは盤面変化と独立の失敗区分として保持する。既存HDSの採否・HOLD・記憶形式とAction認可falseを保つ。

shadowではモデル入力や行動順位へHDS結果を加えない。実際に選ばれた座標を照会するため、Action6を省いたり、恣意的に座標群を先回り列挙したりしない。HDSの実観測更新と、一手先の予測が成立するかを測る段階である。

## 観測・次のゲート

1. CPUでbundle内から実HDSを読み、事前原則5件・公開一手更新・照会非書込・合法性・RESET/死亡・予算・エラー時の視覚継続を確認する。
2. off/controlのGPU推論ready・実ゲーム複数手・3ゲーム終了を確認し、source/config/初期状態・Action/level/WIN・時間・token・例外を採録する。完走しなければ起動/梱包を修正し、同版を無根拠に連打しない。
3. 同条件shadowを実行し、HDS更新/照会/失敗/予算超過、作用前予測と直後結果の対応、rule支持・適用範囲・競合を記録する。score差はHDS計算負荷を含む観測であり、モデルがHDSを利用しないshadowで学習の攻略効果を主張しない。
4. 有効予測が得られなければ、観測表現・想起・学習機構を修正する。支持された予測が得られた後、候補照会toolを通じてモデルの次手へ反映する版を別の対応比較へ進める。
5. モデル＋HDSの行動差と同条件スコア改善、同版再現、公開全25評価を通した候補だけ、公式最高確認値23.86を比較対象としてCompetition Rerunへ進める。公開集合の再利用を未使用ベンチマークの汎化証明とは呼ばない。

コード・bundle・Notebook・metadata・source/input/SDK/model・command・private kernel版と出力hashをrun_idへ結び、off/shadow/後続hintの結果を混同しない。現時点のHDS接続候補のunit結果は実モデル能力・スコア改善を証明しない。

## CPU構築・検査記録

R2構築時の候補は `出力/ARC3-RUN-003-local/C2-078/off-r2/` と `shadow-r2/`。off-r2だけを起動して後述のversion1で完了、shadow-r2は計測不備により起動しない。初版`off/`・`shadow/`は、生成cellの子プロセス用import path区切りがliteral文字列だった不具合を実行前に検出し、**superseded・GPU起動禁止**として保持する。初版をKaggleへ送っていない。

| artifact | SHA-256 |
| --- | --- |
| R2 builder snapshot `出力/ARC3-RUN-003-local/C2-078/source-snapshots/ARC3視覚HDS候補構築-r2.py` | `5ad204658e7d15191b51294e5d3a989938fccb55c04c113c130e82675ba1ed45` |
| native HDS bridge `検証/ARC3視覚HDS接続候補.py` | `1a1c48ad03a3c38668e8b8eba85ef61d8fb86a50143c80c221ba586c22d08617` |
| off-r2 Notebook | `dc2946f11604511becbd0ad9b897eaec4cfc9252a72733fd5b824646e9418d1b` |
| shadow-r2 Notebook | `7fc83b748b3db2f8881e26ada0e8a8732b7b400220f4dd3809fa8a525da16037` |
| off-r2 build manifest | `175808d149c9da773de00b578dd15f58b5e07ae099ca9cf64cdae4e513e2db11` |
| shadow-r2 build manifest | `59500af374c7358c5123b0e3f33d824f625ddf30941d3debd1fe61cec9d1d0c3` |
| 共通HDS source ZIP | `c21517f22af814571982df1412934074b5ff67132715e98419e9e5d85b06d9c4` |

両armのcell6以外の全source cell、id/title以外のmetadata、HDS bundleは一致。ToolAgentとsystem promptは変更せず、共通model seed0をimport前に設定した。新しいprivate kernel IDはoff `tecchannn/arc3-visual-hds-v6-off-pilot`、shadow `tecchannn/arc3-visual-hds-v6-shadow-pilot`。

53 runtime Python filesの構文検査、生成patch cellの隔離CPU実行、3本の実改行を持つimport path、source hash gate、モデルseedのpayload経路を確認。関連regressionは35 tests＋14 subtests、builderの個別試験は8 tests＋7 subtests。後者では実際にpatchした`_execute_action`をstub環境で動かし、off/shadow/constructor失敗でも元Action・fatal payload・個別履歴を保つことを検査した。

さらに、同梱ZIPを別一時フォルダへ展開し、`-I -S`でsite packagesとcheckoutから隔離して実HDSを生成、事前原則5件＋更新1件・照会1件を確認した。証拠 `出力/ARC3-RUN-003-local/C2-078/cpu-bundled-hds-smoke.json` SHA-256 `35d8d74514b55780f359a2d44a077374db1289ca86d226c22c31562d242ea47f`。これは梱包と接続の確認であり、予測能力や攻略効果の実証ではない。

## Private control実行

- run_id: `ARC3-RUN-003-C2-078-OFF-R2-V1`
- kernel: `tecchannn/arc3-visual-hds-v6-off-pilot`、version **1**。新kernelへ1回だけpushし、CLI status `KernelWorkerStatus.RUNNING`を確認。
- command: `%TEMP%/arc3-v6-locked-20261027/Scripts/kaggle.exe kernels push --path 出力/ARC3-RUN-003-local/C2-078/off-r2 --timeout 10800`
- 個別ゲーム制限と共通モデルseedは上表のまま。global kernel timeoutは10,800秒。
- run manifest: `出力/ARC3-RUN-003-local/C2-078/off-r2-private-run.json`、SHA-256 `4baae80fa664e41d20a9e5a543ccb23360e4dc9ae9820df7334bc74915d58988`。
- paired arms事前監査: `出力/ARC3-RUN-003-local/C2-078/arms-preflight-r2.json`、SHA-256 `3d91c27e27c187dde7ebac494446597f403e638682c5b7d14c40439d29bf9e37`。

独立レビューでは、実ToolAgentをCPUで読み、HTTPをmockした実`_chat_completion`のrequest JSONまでseed0が届くことを確認した。証拠 `出力/ARC3-RUN-003-local/C2-078/independent-review-r2.json` SHA-256 `dd2055ae0c693b20c226a8eda30c1e67f237e908b2ddf2fe0615a9e4d768b3cb`。これはGPU推論・得点の証明ではない。現時点の公式最高確認値は過去57577905の23.86、最新57612586は0.03で、本private版の公式得点は存在しない。

次の操作は同じkernel/version1のread-only状態照会。RUNNING/PENDINGを理由に再pushしない。終端COMPLETE後にexact version1出力を取得し、既存C2-059 scorerの`score_run`・`first_event`・`START_FIELDS`を再利用して初期状態・予算・公式local scoreを検査する。旧C2-046の19.309閾値やv28の固定statusは本比較へ流用しない。後述の測定不備を持つshadow-r2は起動せず、controlの起動・実ゲーム進行を確認してからR3の単独予測計測へ進む。

## Version1の引継ぎ照合

`kernels pull .../1`で正確なversion1を読み、手元off-r2の全26セルのtype・joined sourceが一致した。JSONの直列化は異なるためraw bytes同一とは主張しない。照合証拠 `出力/ARC3-RUN-003-local/C2-078/off-r2-remote-v1-verification.json` SHA-256 `0a3a5bbe35d1d63fde4c35ed06f6e9d56463c58773a76916f5db1235761a77c1`。

2026-10-26T22:50:51Zにversion suffix `/1`を付けたCLI照会でもRUNNING。証拠 `off-r2-observation-20261026T225051Z.json` SHA-256 `2e1d21b8705c154f3a9edd1243f2ab19a4330aa1e7ec42ddf1f9767fdd5f3ca2`。同版のlive `.log`取得を一度試したがexit0・取得0件で、readinessやゲーム開始は観測できなかった。この空の取得先を終端出力・採点に使わず、終端まで同じlive-log取得を繰り返さない。再push・shadow開始・公式提出は行っていない。

## 実HDS合成学習による計測不備の確認

2026-10-26T22:55:22Z、事前5件＋合成公開遷移12件を実HDSへ更新し、未使用の合成盤面へ2照会した（計17更新、1.147秒、照会前後の観測数17で不変）。HDSは支持3・反証0の有効な作用番号→公開応答原理を作り、Action1の盤面変化、Action2の可視変化なしを正しく予測した。盤面自体は未使用だが、粗い公開特徴は既知の一文脈と同じであり、新ゲーム能力や未知抽象状態への転移は主張しない。

両照会のtarget `公開応答区分` は有効原理参照あり、競合0・追加観測要求0。native全体は最多色占有帯など別の結果経路の隔離・識別不能により`断定保留`を返す。現在の`render_hint`は全体statusを見て空文字とし、R2 telemetryもその空文字を予測一致計測の条件にしていた。このため、学習された部分予測の正確さを測れない。これはHDSが学習できない証拠ではない。

証拠 `運用/証拠/ARC26-UNIFIED/C2-078_synthetic-learning-probe.json` SHA-256 `b11ca86bb4cb8229accf20ba5b95863cf10d50911dcfabc3cd269dff0b3654a3`。probe source `検証/ARC3視覚HDS合成学習診断.py` SHA-256 `d3946a9c63774c0e8291cbb559c665645fa4f3afb9b922d6e44a802c9e836ee5`。追加した実出力fixture検査は2 tests＋2 subtests。bridge・HDS・実行中Notebookは変更していない。

R3では、対象経路の有効原理参照・競合・観測要求・切詰めの有無で計測できる予測を選び、実行直後の公開結果との一致を数える。native status/HOLD理由・既存hint gate・Action認可falseは保持し、`hint_rendered`と予測精度を別欄にする。モデルの入力・行動は変えない。

**R2/R3を同一sourceの対応比較とは扱わない。** 採点器のbundle/bridge/runtime一致gateは維持する。実行中off-r2は視覚経路の起動・実ゲームcontrolとして完了まで使い、次のshadow-R3は単独の事前予測計測とする。得点差・HDSによる攻略効果を主張する段階では、同じ修正版sourceの新control・candidateと反復測定を改めて必要とする。目的・公式最高23.86を上げる後段gateは変えない。

## R3計測修正版のCPU検査

2026-10-26T23:06:04Z、`off-r3/`と`shadow-r3/`を新規生成。R2→R3のZIP内差分はruntime adapterと内蔵manifestだけで、HDS本体・bridge・事前記憶は全byte同一。Notebook差分は挿入cell6だけ。R3両armの差はmodeと新draftのid/titleだけで、model・prompt・元のSDK作用は保持した。

| artifact | SHA-256 |
| --- | --- |
| R3 builder `検証/ARC3視覚HDS候補構築.py` | `3b1b87bf7075c015c41f0378d7e8b5b42135ec1fa6868886f555565ee270eb1d` |
| off-r3 Notebook | `8d371b04bfb2dbc207307e86d03dcc2ab7271bdb4805fc28b5acea939af01d73` |
| shadow-r3 Notebook | `2c44859bc5754198ce154c4ffb540708d5b5fe5d17a84440ace34902642ebfbe` |
| R3共通bundle | `ed0c13e329c948e774424ebc738eaf2a8c3bb83c0bcdbcf71945a0ac3c5f3766` |
| R3 runtime adapter | `2499e1d42c9176e8cd5c1096d0ebef9374a806ff067dae63d43ae5d5638a2701` |
| `出力/ARC3-RUN-003-local/C2-078/arms-preflight-r3.json` | `7de8ad245854516ca611f1534df4c7330d1ae44976385c5c22467ac514166c3d` |

対象経路の事前予測は`target_qualified_unique_predictions_observed`、実結果との一致は`target_qualified_unique_prediction_matches`へ記録する。既存のrender_hint由来の計測、native全体status/HOLD理由、複数候補・測定できない理由は別欄に残す。対象の競合・追加観測要求・有効原理参照・切詰めを検査するため、native HOLDを出力へ書き換える処理ではない。

targeted 11 tests＋17 subtests、53 Python filesの構文検査、生成cellのCPU実行、79ファイルのsource guardが通過。同じ実HDS合成fixtureの2件を計測でき、native query辞書と空のhintは不変だった。実ゲームの一致率、行動への効果、得点改善は未測定。

構築時の指定draft IDは`tecchannn/arc3-visual-hds-v6-off-r3-pilot`と`tecchannn/arc3-visual-hds-v6-shadow-r3-pilot`。その時点では両方未pushだった。後述のshadow-r3起動ではKaggleがtitle由来の実行先を返したため、実行先とsourceを改めて照合した。off-r3もtitleと指定IDが一致していないので、この凍結artifactをそのまま起動しない。shadowは単独の事前予測計測として扱い、R2とのpaired deltaを計算しない。

## 終端出力の採点器

`検証/ARC3視覚HDS対応採点.py`は単独off/shadowと厳密な同sourceペアを扱う。exact versionのCOMPLETE、Notebook/metadata/bundle、取得対象ファイルのbyte/hash、3ゲームの開始公開状態・実Action履歴・HDS sidecarを検査し、既存の公式local scorerで0点を含めて再計算する。累積clockはゲーム別差分に直し、各ゲームのモデル生成tokenが正であることを要求する。失敗時も得点と証拠は残し、有効な対照試験とは判定しない。

off-r2採点時点のscorer SHA-256 `49874aff3eb2f5b188d5d09ab0f61f44e7f69b02b93e2c6ee8c137b57dfcc530`。21契約tests・Ruff通過、証拠 `出力/ARC3-RUN-003-local/C2-078/scorecard-preflight-20261027-r2.json` SHA-256 `e17878cf6b23ae29faa5f00d9be02353c9fc1bcfd1ab916ce1d81b945d18490c`。この末尾r2は採点器検査の改版で、Notebookのarm名ではない。同証拠にR3の独立byte比較・凍結native fixtureの検査を併記した。

終端後は`kernels output tecchannn/arc3-visual-hds-v6-off-pilot/1`を新しい取得先へ実行し、benchmark・events・visual-hds sidecar・log・git_statusだけを選択取得する。全出力取得とは主張しない。取得manifestは`arc26-arc3-private-kernel-terminal-output.v1`とし、採点器の`output_manifest_digest`で列挙ファイルのdigestを作る。空のlive-log取得先は使用しない。

```powershell
& "$env:TEMP/arc3-v6-locked-20261027/Scripts/python.exe" 検証/ARC3視覚HDS対応採点.py --single-retrieval <新しい終端manifest.json> --single-build 出力/ARC3-RUN-003-local/C2-078/off-r2/build-manifest.json --single-output-root <新しいexact-version出力先> --single-version 1 --output <新しいscorecard.json>
```

2026-10-26T23:09:28Zのexact `/1`照会は引き続きRUNNING、exit0。証拠 `出力/ARC3-RUN-003-local/C2-078/off-r2-observation-20261026T230928Z.json` SHA-256 `a4336f0d7d5a932901ce74aa734409e33571a737ee891483520602363093b16e`。新push・公式提出・再実行はしていない。

## 公開ゲームの逐次予測診断

2026-10-26T23:22:20Z、凍結R3 bundleと実公開SDKを用い、履歴v5 benchmarkの先頭3ゲームをseed2701で各80回、計240回操作した。選択器はHDSに依存しない一様な合法Actionで、Action6は公開盤面内の座標を選ぶ。各ゲームでHDSを新規生成し、作用前照会→SDK一回→直後の公開応答更新を行った。RESET1回を教師から除き、GAME_OVER1件はそのまま応答として保持した。

| 指標 | 観測値 |
| --- | --- |
| 非RESETの実公開応答 | 239 |
| 対象経路の一意な有効原理付き予測 | 56 / 239（coverage 23.43%） |
| その予測と直後結果の一致 | 52 / 56（92.86%） |
| 同じ56件の厳密な過去多数派との一致 | 48 / 56（85.71%） |
| native全体が断定保留 | 239 / 239 |
| render_hint非空 | 0 |
| 盤面変化 / 無変化 / GAME_OVER | 195 / 43 / 1 |
| level進行 / WIN | 0 / 0 |

過去多数派は同じゲームでその作用より前に受けた応答だけを数え、HDSの予測が出た同一stepで比較した。これは一手先の公開応答予測の観測で、攻略スコアやHDSによる行動改善ではない。盤面変化を有益な攻略と同一視しない。公開集合を再利用しており、未知ゲーム汎化の証明ではない。

239更新・239照会・事前原則15更新はすべて成功、HDSエラー・契約エラー・時間予算超過・予算による拒否要求は0。2ゲームは80回のupdate/query上限へ到達した。HDS処理135.233秒、全体145.787秒。SDKはarc-agi0.9.8 / arcengine0.9.3。生盤面・座標・Action列・game IDはこの診断結果に保存していない。

**本診断の3ゲームはWindowsローカルSDKの列挙先頭3件と異なり、実行中GPU pilotとの一致は未確認。** 同じR3 bundleの接続診断として扱い、GPU対照版との対応比較には使わない。選択元v5 benchmark SHA-256 `7237a2d2150820ee2aadc8ba986dcb67a12e495bd934bd686583b1cd32ebdcd2`。

証拠 `運用/証拠/ARC26-UNIFIED/C2-078_public-prequential-hds-seed2701.json` SHA-256 `ecb61ef1ff413cad958118a7c90ae3054353ac11069565e83be510816626a021`。runner `検証/ARC3視覚HDS公開逐次予測診断.py` SHA-256 `b49524127e53254bc00bc3498eb3ee45ee29332900beee1969a3d0e009b7ada1`。過去多数派の時系列契約はtargeted 2 tests通過。

## native照会の範囲と次の候補

現行native APIは結果経路を指定できない。予測生成は境界・既知項目を見て絞る一方、`HDS/学習系統/v0.4.2/hds学習系統/実行系.py:655`では全境界の有効・隔離原理を集め、`適応.py:191`の識別不能判定には現在の照会項目を渡していない。凍結合成例では、応答の予測は成立していても、事前記憶のmetadata・既知の実行前項目・最多色占有帯が全体の断定保留を生んでいた。

R3の予測計測は、有効原理参照・予測競合・観測要求などのguardを通った返却値の一致率である。bridge要約はnativeの係争中原理群と識別不能群の全詳細を保存していないため、**対象についてすべての保留条件を通過した、とは解釈しない**。実ゲーム239照会の保留をすべて無関係な理由と断定することもできない。

次のC2-079は、nativeが任意の結果経路スコープについて予測・競合・観測不足・隔離・識別不能を一貫して判断する候補を、凍結sourceに対するpatchとTEMP実行だけで検証する。既定の全体照会とそのHOLDを保持し、対象に根拠がなければ採用しない。canonical HDS・bridge・R3・実行中GPUは変更せず、後処理でHOLDを出力へ書き換えない。攻略への利用・得点改善はその後の別比較を必要とする。

## Private control version1の終端結果

2026-10-26T23:28:20Zにexact `tecchannn/arc3-visual-hds-v6-off-pilot/1`がCOMPLETE。11選択ファイル・7,741,807bytesを新規取得し、0点を含めたsaved scoreと公式local計算を全件照合した。

- 公開3ゲームoffline RHAE平均 **8.333333333**、4/21level、WIN0、実Action240。
- 3/3ゲームでモデル生成を観測、history generated tokens195,480、各80Action以内。benchmark elapsed1464.963秒、最長game581.259秒で1200秒予算内。
- off sidecar3件でHDS呼出し0・adapter error0、実作用履歴240件と一致。execution/integration gateは有効。
- kernel logにRTX PRO 6000 Blackwell Server Edition、serve.logに22:57:03のApplication startup completeと固定Qwen3.8-Flash-Next model pathを確認。
- 終端取得manifest SHA-256 `5ba043dd55eb22e243866550efb6ac95a176755318dad20703dd569c39c93092`。
- scorecard `出力/ARC3-RUN-003-local/C2-078/off-r2-terminal-v1-scorecard-20261026T232820Z.json` SHA-256 `dbdab27540d9daf0339a6b6e37d9f7777230544bcc8eab86e10ffdd1cfac04d6`。
- benchmark SHA-256 `1b83e9bc402a278171f3db76c1d3bd476908857563a89d3e330ba6a41ce5d0fc`。

これは新しい公開3ゲームcontrolであり、公式23.86や異なるゲーム集合の旧private値との能力差ではない。公式提出・quota利用なし。

## Private shadow-R3 version1の開始と実行先照合

2026-10-26T23:34:17ZにR3 shadowを1回push、version1成功。指定idは`tecchannn/arc3-visual-hds-v6-shadow-r3-pilot`だったが、titleをR3表記へ変更しておらず、Kaggleは`tecchannn/arc3-visual-hds-v6-shadow-pilot`を返した。再pushせず、そのactual `/1`をpullし、26cellのtype/sourceが凍結R3と全一致した。remote metadataの差はid、code_file名、server id_no、既定のenable_tpu/keywordsだけで、GPU・Internet・model/dataset等は同じだった。

元のmetadata・build・push request/receiptは保持し、別のidentity照合証拠を作った。identity proof `出力/ARC3-RUN-003-local/C2-078/shadow-r3-v1-identity-verification.json` SHA-256 `c2435ad16d7f3b45315744ce638052f8c3fb6bb04a977f990262125d41d8cb47`。終端の採点器はこのproofからsource・metadata・返却URL/versionを再検査し、根拠のない別kernelを受け付けない。R2/R3のsource一致gateを緩めない。

run manifest `出力/ARC3-RUN-003-local/C2-078/shadow-r3-private-run.json` SHA-256 `830a9d96a6cd02db82f0efa02b0819245679857f69419b92c978d4dcabe14692`。23:39:15Zのactual `/1`はRUNNING、公開3ゲーム・model seed0・80Action/1200秒/game、HDS80updates/80queries/120秒/game、global10800秒。モデルready・HDS実ゲーム精度・得点はまだ観測していない。

次は **`tecchannn/arc3-visual-hds-v6-shadow-pilot/1`のみ**をread-only追跡する。指定した未作成r3 slugを再pushせず、既存off-r3も起動しない。終端後にactual exact version1の選択出力を新規取得し、identity証拠付きで単独計測する。公式Submission/Competition Rerunなし、R2/R3のpaired score gainは主張しない。

### 返却された実行先を採点する検査

採点器は、通常のkernel一致検査を保持した上で、別IDの場合だけ明示されたidentity証拠を再検証する。receiptの返却URL/version、requestのsource hash、remote Notebook全26cell・raw hash、remote metadataを照合し、任意の別kernelを許す仕組みにはしていない。凍結R3 metadataは編集していない。

現scorer SHA-256 `6ca19fcb4860b257e71c292ca77e7d775660f0c8f2f759bc4a0c984d6544db6a`、32 tests・Ruff通過。旧scorer/testsはsource-snapshotsへ保存した。新scorerで実off-r2を再計算してもRHAE8.333333333・4level・240Action・3ゲーム生成・integration有効を維持。証拠 `出力/ARC3-RUN-003-local/C2-078/scorecard-preflight-20261027-alias-r3.json` SHA-256 `ab6fa23d83b9f9c23aff69e037f4f8f477b363c86e76811cb6df3cb61b4cdd67`。旧scorecardは保持した。

shadow終端manifestはactual kernelと凍結localR3の`candidate_*`hashを使用し、以下を追加する。

```json
{
  "identity_verification": "出力/ARC3-RUN-003-local/C2-078/shadow-r3-v1-identity-verification.json",
  "identity_verification_sha256": "c2435ad16d7f3b45315744ce638052f8c3fb6bb04a977f990262125d41d8cb47"
}
```

### C2-079の後続結果

native対象経路照会はTEMPで同じ239観測へ比較し、全体HOLD239→対象出力4/HOLD235となったが、予測は同じ56件・52一致で改善しなかった。対象内の隔離・識別不能が残る。native出力4件だけの精度は未集計でUNKNOWN、攻略への採用・正本反映はしない。次はモデルが実際に進行した公開遷移の診断へ進む。詳細 `運用/ARC3-RUN-003/C2-079_native対象経路照会_公開逐次比較.md`。

2026-10-26T23:54:48Zもactual shadow `/1`はRUNNING、exit0。証拠 `出力/ARC3-RUN-003-local/C2-078/shadow-r3-observation-20261026T235448Z.json` SHA-256 `8d0931adb166525b45ba6f672bedaabf212f37a909328cbce41231839c3b0228`。diff-check有効、保護2ファイル差分0、staged0。モデル用`hds_query(candidate)`は既存Python sandbox/sessionを使う設計までで未実装。まずC2-080の公開進行遷移を縮小projectionで診断する。

## Private shadow-R3 version1の終端結果

2026-10-27T00:18:14Z、actual `tecchannn/arc3-visual-hds-v6-shadow-pilot/1`がCOMPLETE。指定r3 IDとのidentity証拠・26cell・runtime metadataを再検査し、新しい11選択出力7,985,899bytesを単独採点した。

- 公開3ゲームoffline RHAE平均 **5.952380952**、3/21level、WIN0、実Action240。全3ゲームでモデル生成、history generated tokens222,462。
- benchmark elapsed1687.898秒、最長game621.703秒で1200秒予算内。execution/integration gateは有効。
- HDSは238更新・238照会・prior15更新を成功、adapter/HDS error0、HDS実時間20.592秒、予算による拒否要求0。
- 240実Action中、RESET/automaticとして同じ2件を除外し、238応答を学習。内訳は盤面変化226・無変化8・level進行3・GAME_OVER1。2種類のskip counterを足して4件除外とは解釈しない。
- native238照会はすべて断定保留。返却された対象の一意な有効原理付き予測は75件、71一致。これはすべてのnative保留条件を通過した値を意味しない。render_hint由来の測定は0件でUNKNOWNのまま。

R3は予測をstep別に保存していないため、この75件と同じstepでの厳密な過去多数派を復元できない。71/75だけで多数派より有用・攻略に寄与したとは主張しない。C2-081では未照会stepを含む応答receiptと、model response/inspection/候補/実Actionの対応を保存する。

| 証拠 | SHA-256 |
| --- | --- |
| `shadow-r3-terminal-v1-retrieval-20261027T001814Z.json` | `b83154eb426713a418fee40f3102926cd6727bcbab50a160f4b64eae73ed025a` |
| `shadow-r3-terminal-v1-scorecard-20261027T001814Z.json` | `9c64962c947e53df0c8ee5d6f5bfd90233127af11a9944851e2beba03b78f7e2` |
| exact benchmark | `59c026cc26ebe33707dc685618428d46a3e760d1a827e622eda30ac6f11ccb19` |

各ファイルは`出力/ARC3-RUN-003-local/C2-078/`以下。これはshadow単独観測で、HDS情報による行動差も公式得点も存在しない。off-r2とのsource一致gateを緩めず、得点差をHDSの効果に帰属しない。両version1の追跡は終端として終了し、再起動しない。

後続の実モデル遷移診断C2-080はHDS30/33一致に対し同step多数派31/33で、旧応答ヒントの優位はなかった。C2-082ではAction6の80件すべてが全体変化となる一方、26件はtarget7×7変化0だった。現在は元の進行/失敗応答を保持し、局所と遠隔の効果を分けて学ぶC2-083をLOCAL診断中。モデルが未確定根拠を読んで独立探索するC2-081はCPU候補で、未push。公式最高確認値23.86の更新へ最適化を継続する。
