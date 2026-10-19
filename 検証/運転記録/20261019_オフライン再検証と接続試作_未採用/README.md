# 2026-10-19 オフライン再検証と未採用の接続試作

## 目的・観測・原因・変更

保存済みの基底と保存失敗捕捉を復旧後の環境で独立再検証し、新しい接続試作の成立範囲と失敗を保持する。対象は完成済みの三作業だけで、後続の意味的候補経路の再接続作業は含まない。

- 元の基底は 38 tests が成立。ただし 12 件は残存する弱点の再現である。
- 元の保存捕捉は同じ 38 件と追加 25 件からなる 63 tests が成立。38+63 を 101 個の独立 test と数えない。
- 新しい接続試作は最終 45 tests が成立し、34 件の negative/subtest record を保持する。これは注入した mock を使う、一手だけの保存・判断束縛の検査である。
- 独立レビューが発見した三欠陥、すなわち保存 callback の再入 HOLD 後に照会が続くこと、保存した出力と後から変化した出力状態の混用、由来の deepcopy 失敗で lock が残ることを修正し、独立再検査が成立した。

原因と変更は同梱の原報告と修正前後の source/probe に残した。初回 fixture error、修正前の出力、失敗記録を後の成功で上書きしていない。試作は NOT_ADOPTED。native 起動は HOLD のままである。

## previous / current / delta / regression

previous は main `ebd00822db48995e024fe3ea15ea71c976edac34`。既存の基底・保存捕捉 package は既に main にある。

前 checkpoint の [保存範囲索引](../20261019_保存範囲索引/README.md) は当時の snapshot として保持する。回収原本 13/14 本と公式接続の安全化派生物はそのままで、本書の package が既存の新規証拠 3 package に追加される。

current は完成済みの新規 source、tests、再検証結果、独立レビューと失敗履歴を、非 runtime の運転記録として追加した状態である。delta はオフライン境界検査と三欠陥修正の証拠であり、学習・攻略能力の増分ではない。

regression として元 package の 83 ファイル不変、新規 dependency manifest の 32 input + 23 delivery の計 55 pins 一致を確認した。公開境界の二つの小さな自作依存を試作の閉鎖 package 内に含めた。既存 main のファイル、HDS、AGENTS、権限、現在状態は変更していない。

## 内容と再検証

`arc-offline-restart-checkpoint-20261019.tar.gz` は、`payload_manifest.json` に固定した 51 ファイルと包装 metadata を含む。三作業の元ディレクトリ名を保つ。全 member の byte 数と SHA256 は `archive_verification.json` で追跡する。raw failure JSON、pre-fix source、独立 probe とログを含み、summary だけの保存ではない。

新しい試作の純粋 test は展開先 `arc-pinned-restart-20261019/README.md` の手順に従う。実行時には新しい結果名を使い、既存結果を上書きしない。本保存作業ではテストや source を再実行していない。

元基底・保存捕捉の再検査を再現する場合は、`payload_manifest.json` の `existing_dependencies` が示す、既に main にある正確な二つの archive も必要である。これらの大きな展開 state/core と既存履歴は重複同梱していない。各原 manifest の絶対 path は当時の provenance であり、任意の新しい配置でそのまま動くという保証ではない。復旧先との対応と byte identity を確認してから、別の限定作業として検査する。

## limitations

native HDS import、restore、Query、Teach、SDK、live Action はこの三作業と保存工程で実行していない。mock の照会・Action 回数を native 実績と数えない。183 経験・16 原理・counter 6647 は保存 envelope の観測であり、native 復元ではない。歴史的認証 fresh 1/183 は再測定しておらず、全 game WIN や能力改善を主張しない。

この試作は作用番号の mock 契約であり、既存 semantic_entry、goalset、preservation の構造的候補・座標推論の代替ではない。4096 座標の合法性列挙は、構造・効果・保存条件の全検証を意味しない。意味的経路への接続、native codec・耐障害保存、実 workload の資源、実教師由来と HDS 判断からの Action 束縛は別の gate である。

fresh043 と 358,669-byte 歴史解析の欠落は旧 run の完全再現を妨げるが、新しく名前を付けて依存を固定した接続作業を永久に止める理由にはしない。新しい結果を欠落した歴史原本と読み替えない。
