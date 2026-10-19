# 2026-10-19 観測された効果から候補コマンドへの対応学習：Inverse78 保存

状態：独立監査 BOUNDED NATIVE EVIDENCE PASS。非公開の保存用成果物。公開 main への反映は、別件の歴史的 HDS 文書の範囲確認が終わるまで停止中。
この保存は実験証拠の閉鎖であり、runtime 採用・Action 実行の承認ではない。

## 目的
既に測定・監査した公開履歴の効果記述から、支持された候補コマンド種別と逆向きの対応を HDS v0.4.2 の学習機構に保持できるかを、固定入力・完全な状態差分・原記録で確認する。成立した限定的結果、失敗した準備検証、適用境界を一緒に残す。

## 観測と原因
測定対象は既存の 631 action 文脈。効果記述を action ID、分類ラベル、進捗、成功判定から独立に前後 scene から導出した。
- palette/tool 色変更 98、wide target 変更 90、その他・不明・不変・競合 443。
- reset / 非対応操作の対照 26 は 631 文脈の内数で、別の独立試行ではない。
- 6 個の録画／効果別 cohort にまとめた。新たな環境観測は 0。既存録画の相関した集約である。
- 同色のため不変だった click 3 件、wide paint で不変だった 12 件も元 corpus に保持する。
- 効果の分類後に、対応した 188 行の before scope/status と観測されたコマンドの利用可能性を検証した。矛盾を消すための先行フィルタではない。

学習前の 4 問は「出力 / 適用外」で予測が空だった。HOLD と言い換えない。今回の入力は既存効果語彙と観測済みのコマンド値の対応であり、未見の領域や新規環境を試していない。

## 変更、previous / current / delta
固定された 36 Query → 6 Teach（処理）→ 同一の 36 Query、計 78 呼び出しを 1 回実行した。
- previous：210 experiences、29 principle records、counter 6822。
- current：216 experiences、31 principle records、counter 6894。
- delta：6 experiences、2 個の方向別「決定的対応関係」v1、Query counter +72。
- palette/tool-change 効果 → strict integer 6、wide-target-change 効果 → strict integer 5。逆向き 2 問は対応する効果文字列を返す。
- 2 原理の保存済み supports は 211–213。教師 3 で 1 adaptation。残り 5 教師の結果は接続途上。後続 experiences 214–216 も保持・評価されたが、原理版や supports の更新はない。
- 4 問の学習後予測は正しい型と値で一致。4 値は全て観測済みで、未見値への転移試験ではない。

完全な原記録は 243 frames（234 call records + 9 snapshot indices）、9 個の native 全状態、入力・生の返答・完全な追加差分を含む。2 つの Query-only 区間は、対応する 2 counter の +36 以外の状態変化がないことを検証した。既存 ledger / principle / state-history の全 prefix を比較し、独立導出した全 native delta が producer の差分と一致した。

## regression
合意した既存 32 入力について、状態・予測・競合・追加観測要求・識別不能・係争中原理・断定保留理由・学習成立状態の関連 projection は全て不変。生の返答 32 件は全て異なり、全出力一致を主張しない。旧 active principle summary の prefix は保持。
39 個の source/input pins、以前の Teach 181 files、identity 105 files、COPY 114 files、および今回の freeze を独立監査で再検証した。この smoke set は全過去成功やゲーム全体の回帰試験ではない。

## 保存範囲と履歴
payload_manifest.json の 5 個の閉鎖済み root、230 files / 107,001,988 bytes を保存する。各 source、archive path、bytes、SHA256 を固定した。
1. arc-native-inverse-20261019：90 freeze entries、freeze 自身、closure02 の stdout / stderr / exit status。
2. arc-inverse-operator-teachers-20261019：631 文脈の測定、教師と入力、導出源と manifest。
3. arc-inverse-operator-review-20261019：全 corpus の独立意味検証。
4. arc-inverse-bound-review-20261019：prepare / template / closed_plan01 の失敗を含む履歴、修正後 closed_plan02。
5. arc-inverse-launch-review-20261019：準備検証と独立 outcome audit の全閉鎖済み記録。

今回の native / preparation 本体に失敗試行はないが、growth reviewer の初期のファイル名仮定などの失敗 leaf は削除していない。producer の REVIEW_PENDING は原 bytes のまま残し、後続 reviewer PASS と時系列で読む。外部の過去単位に存在する欠落を今回の完全保存で補ったとは主張しない。

学習機構本体、以前の全 raw corpus、COPY 等の元 archive は既存の hash 参照とし、無関係な再帰コピーをしない。現在進行中の TURN、opaque な SDK / 公式ゲーム実装・stderr、非公開 HDS 文書開示監査とその raw 取得記録は含めない。実装 source と学習状態は、原典 HDS 文書とは区別して内容審査する。

## resource / 保存検証
実行の maximum state 6,535,400 B、growth 211,180 B。state proof 6,877,589 B < 8 MiB。maximum reply 51,373 B < proof 66,679 B < 72 KiB。evidence 使用 3,983,841 B、peak child RSS 92,684 KiB、wall 12.74915376098943 s。unit < 96 MiB、集計 < 672 MiB。failure / emergency は空、failure state は zero。
native Save が予約領域を truncate するため、これらは既知 writer の論理的上限と観測値であり、物理 ENOSPC 時の保存保証や敵対コード隔離の証明ではない。

保存担当は native を再実行せず、原ファイルの hash、独立内容審査、全 tar member の bytes / SHA256、xz integrity check / EOF を検証する。予約領域の zero tail も切り捨てず可逆圧縮する。原ファイルの再検証結果と archive の正確な identity は別の archive_manifest / verification / Library receipt に記録する。

## limitations
- 学習されたのは、限定された歴史的効果条件から支持される候補コマンド種別への対応と逆向き対応。普遍法則、値の同一性、必要性、唯一の原因、fresh applicability は未証明。
- 欲しい効果を Query に与えることは goal/program feature の指定であり、未実行効果が既に起きたという観測事実ではない。
- role / scene 解釈、paired endpoint、wide geometry、cohort grouping、効果語彙は固定した測定の事前知識。これらが学習されたとは扱わない。
- offline checked_endpoint は flag の存在や live packet の identity を厳格に認証する wrapper ではない。既知の missing-flag 制限は未解消で、全 corpus caller の前提を外して利用できない。
- コマンド 5 / 6 を実行すれば常に当該効果になるとは証明していない。保持した 443 の非該当文脈、不変・不明例を消さない。
- 現在の goal の正しさ、座標、合法引数、利用可能性、安全な Action dispatch は別途確認が必要。fresh の観測・候補・効果・action binding と明示承認が必要。
- SDK / Action は 0。環境内の新しい成功、複数ゲームへの汎化、速度向上、full-game WIN の主張はない。216 は experiences であり、level clear 数ではない。
- 以前の別実験で認証済みの fresh clear は 1/183 で、今回の増分ではない。今回の証拠を 183 level 攻略や全証拠復元と読み替えない。
- HDS core、AGENTS、権限階層、現在状態、runtime 採用経路は変更しない。公開先 main の基準は 2ca6531908551755988ade040840362684c96b14。公開は別件の確認待ち。


## 保存形式の修正履歴
最初の gzip 作成は payload 用 2.75 MiB 上限で停止した。原 script・stdout・stderr・exit 1、2,875,902 B の不完全 archive と作成時 manifest を保存し、成功成果物に数えない。元ファイル名から inverse78-gzip-cap-failure.partial.tar.gz へ bytes 不変で改名した。Counting sink による全量測定後、完全な xz へ変更する。内容・状態・zero tail の省略はない。増枠後の inverse 全 archive / receipt 上限は 4 MiB（不完全 gzip も含む）。全体は archive 88 MiB + metadata 16 MiB、旧 mirror 予約 12,467,596 B を維持。変更前 README とその内容審査結果を残し、今回の形式修正は追加審査で結び付ける。
