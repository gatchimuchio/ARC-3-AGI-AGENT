# Codex実行指示書：ARC-AGI-3を実働するHDS学習Agentへ改修し、公式得点を上げ続けよ v3.0

- 指示ID：`ARC3-RUN-003`／2026-10-28（JST）
- 対象：`gatchimuchio/ARC-3-AGI-AGENT`
- 参照正本：`01_ARC3_仕様書_v3.md`、`02_ARC3_工程表_v3.md`。この3点は**一体の実行契約**であり、過去v1/v2と矛盾する部分は本版を優先。ただしOwner現行指示、`AGENTS.md`、保護規則、公式規約を上書きしない。
- 本指示の委任範囲：リポの監査、通常の実装・試験・記録、既に許可されたKaggleアカウントでのNotebook/Competition Rerun、適法なエラー修復と同日再試行、継続改善。新たな権限取得や非公開中核の公開は許可しない。

## 0. 最上位命令：何を完成と呼ぶか

**Ownerの目的は「HDSラーニングマシンでARC3を攻略し、公式提出でスコアを出し、性能を伸ばして優勝すること」。提出経路の形式PASSだけでは不十分である。**

1. 今の`接続/ARC3提出agent.py`は`MAX_ACTIONS=1`でHOLDし、初期化以上の行動をしない。**これを高性能Agentと誤認してはならない。** SDKが操作し、実際にレベルを突破するAgentを実装せよ。
2. `HDS/学習系統/v0.4.2`・`記憶/事前記憶/v0.4`を最初に棚卸しし、**実際の候補選択・作用・状態更新へ接続せよ**。HDSはimport/ログ用の飾りではない。
3. 2026-10-22のCompetition Rerun提出ID **`57527856`** は記録上`PENDING`。**最初に現在の終端状態、数値score・errorDetails、利用枠を照会**し、不明のまま「公式提出成立」としない。
4. 公式スコアの数値が正常に確定した提出だけを`SCORED_ACCEPTED`と呼ぶ。`0.00`も受理済み低得点。`ERROR`、timeout、数値なしは**採点成立ではない**。原因を特定し、**Kaggleが再送を認める限り同日中でも何度でも修理して再提出**せよ。人工的な一日一再試行制限を追加するな。
5. 本物のAgentで公開ゲームを動かし、その結果を固定してから、改善を公式RHAEに接続せよ。**Notebookの1行`score=1`のdummy Parquet、`SAVE & RUN ALL COMPLETE`、11件テストPASSをスコア・学習実証へすり替えるな。**
6. **優勝ペース**は公式RHAEと首位との差、公開ゲーム全体のレベル突破・Action効率で測れ。公開首位75.56%（10/28参考）と距離が大きい場合、細かな既存HOLDのテスト拡充を競争力向上と呼ぶな。
7. エラー・HOLD・低得点・チケット完了は通常の停止理由ではない。状態を保存し、根拠のある次の改修/公式評価へ移る。**古い「E5個別承認待ち」「E5後の開発停止」は撤回済み**。他方、保護対象・秘密・規約・権限は守る。

## 1. 着手直後：観測を省略せず現在地を確定

1. Ownerのこの指示文、repo `AGENTS.md`、`制御/現在状態.json`、`運用/ARC3文書正本.md`、本3点、関連する現行SDK/Runner/Notebookコードを**その時点で**読み直す。2026-10-28観測SHA `8667e9b...`は出発点であって最新保証ではない。
2. 現在HEAD、`git status`、本人の未コミット差分、保護対象、現在コード、Notebook slug/version、運用実績を確認。勝手にcheckout/reset・force push・旧成果上書き・過去証拠の削除をしない。
3. Kaggleに既存の正規ログインがあるなら次を照合：エントリー状況、`57527856`のstatus/errorDetails/score、Notebook version 5と後続版、submission-limits、最終選択状況、公式締切、CPU/GPU利用可否、最新首位。接続方法はKaggle CLI/API/MCP等の**既存認可済み手段**から選ぶ。
4. 同提出IDが公式終端数値得点なら旧基準線として固定し、重複提出しない。終端エラーならログ・残枠を確認して修復し、現在の有効な攻略版を用意する。未終端なら追跡しつつ、Agentの本体開発を並走する。
5. 過去の14/183・1/25（10/20）、2026-08-03別提出の0.06、古い18.82%ローカル結果、HDS記憶の成功軌跡と、**現行採点・現行Agentの能力を別の行に記録**。同条件で再現したものだけを現在値に昇格。
6. 公式ARC3 SDKの現行`Agent.main/is_done/choose_action/take_action`、`FrameData`、`GameAction`、`OperationMode.COMPETITION`、Action6 xy、RESET/ GAME_OVERを、配布Starter・実機と突き合わせる。付属ZIPの旧Starterと現在版が違えば現在の公式仕様を優先。

### 初回の観測報告（この後、許可待ちを挟まずP2へ）

```text
ARC3-RUN-003 / P0-P1
現行 git SHA・dirty tree：
現行 Notebook slug/version：
公式既存提出 57527856：status / errorDetails / 数値score / 時刻
当日受理枠・残枠：実測 / 未取得
現在の正本・保護状態：
現行Agent：Action実行可能 / HOLD only / その他（証拠）
旧成果の再現性：実測 / 参考値 / 未確認
競技制約：9h / Internet無効 / Competition mode / 締切
首位・本人得点・差：実測値 / 未確認
最初に修復する具体的欠陥：
次の自動工程：P2→P3→P4→P5/P6/P7→P8→P9
```

## 2. 最初に直す実コードと責任の対応

| 対象 | 観測された欠陥・未接続 | 指示する変更方向 | 先行受入試験 |
|---|---|---|---|
| `接続/ARC3提出agent.py` | `MAX_ACTIONS=1`、HDS照会後HOLD終了、RESET以外発行不能 | 「公式観測→判断→GameAction→帰還」の連続動作へ。HOLDとゲーム終了を分離。予算と継続判断を追加 | 異なるActionを最低複数step、有効な観測・理由を残す |
| `接続/ARC3境界.py` | `作用を排出する`が独自に`env.step`。Runnerも`take_action`でstep | Action検査・変換と実行責務を分離。**一つのAction送信に一つのstepのみ**。既存機能を壊さず回帰 | mock step counter = 実Action数、重複ゼロ |
| `接続/共通観測経路.py`および構造・配置解析資産 | HDS候補照会はあるが有効な次行動へ転換されない | 観測から物体/関係/状態差分を形成し、仮説・操作候補をHDSへ渡す。既存処理を再利用 | 同一観測/前Action/結果が対応、候補が変わる |
| `HDS/学習系統/v0.4.2` | 包装されているが行動選択・実際の経験更新への寄与不明 | 既存公開API/責務を検証し、Domain Adapterから利用。中核の書換えが必要なら根拠と権限を別途確認 | HDS有無で判断変更、説明可能な差分 |
| `記憶/事前記憶/v0.4` | 生成器の現バンドルでは除外 | 合法な一般化ルール/失敗署名のみ梱包・参照可能に。個別ゲーム答えlookupは禁止 | memory hash・候補順位・転移への寄与測定 |
| `道具/ARC3提出物構築.py` | HOLD用slug、1行dummy Parquet、静的import依存のみ | 実動作Agentと必要なオフライン依存を決定的に梱包。E4 dummyと競技本採点経路を明確分離。名前・説明を実体と整合 | 再生成hash、Kaggle Save&Run、Competition Rerun実得点 |
| `検証/test_ARC3提出物構築.py`とHOLD期待テスト | 0操作/1行dummyがPASSになっている | 既存HOLD基線の記録テストは履歴として保存。現行性能テストは**実Action/level/帰還/合法性**へ更新。ゲーム特化化しない | ダミーPASSを攻略PASSと報告しない |
| `検証/運転記録/*`、`運用/ARC3文書正本.md` | v2旧目的・E5受付時点が残る | v3受領・SHA・再開点を追記、v1/v2と旧submit記録は履歴保存。保護ファイルに触れない | 新旧の版・時刻・根拠が混在しない |

**注意：** `AGENTS.md`と`制御/現在状態.json`はOwner明示承認なしに変更しない。特に`自動遷移:false`を独断でtrueに編集し、その編集を根拠に権限を作らない。Ownerの明示した継続作業の範囲では、保護ファイルをそのまま保ち、工程表に従って実装・再試験を進める。

## 3. 実動作Agentの行動契約（実装で曖昧化するな）

### 3.1 一回の意思決定

1. 現行`arc_env.observation_space`を正しいタイミングで取得し、`FrameData`から観測通番・frame・state・levels・available_actionsを正規化。初期ダミー`FrameData`を現在観測と取り違えない。
2. 前回の実Actionと新観測の対応から状態変化を抽出。進捗/無変化/逆効果/レベル上昇/ゲーム終了を識別し、直前の因果仮説を更新。
3. 既存の接続/構造処理から対象物・関係・行動可能性・目標仮説・失敗署名を抽出。ゲーム/レベルIDによる固定手順は作らない。
4. 有望な複数Action候補を生成：目的への計画Action、低リスクな情報獲得Action、状態回復/再計画Action。ACTION6は意味あるx/y候補から作る。
5. HDSが判断に寄与した部分を記録し、未確定の認識仮説は未確定のまま保持する。HDSによる確定根拠と**明示的に合法な暫定探索Gate**を別系統とする。探索Gateは候補の適法性・観測鮮度・行動数/時間予算・期待情報価値を判定。
6. `ActionDispatch`を経てSDKが期待する`GameAction`と正しい引数を**返すだけ**。Runnerの`take_action`以外からstepしない。Action6の座標とGameAction Enum共有変異を検証し、別ゲームに古い引数を残さない。
7. 実step後は新観測を帰還させ、次のループへ。HDSのHOLDを勝手に`WIN`や停止へマップしない。停止はWIN/実環境終端/合法Action不存在/ゲーム・全体の予算・規約上の条件から決める。

### 3.2 Action候補の原則

- 1–4は典型的な上下左右のインターフェースだが、ゲームによる意味の違いを観測で検証。勝手な固定操作列や反復`ACTION1`を汎用ソルバーと呼ばない。
- 無進捗は「現在の仮説の反例」。同画面で反復しただけなら行動優先度を下げ、目標・操作意味・局所変数のどこが誤ったかを更新。
- 目標は`levels_completed`の変化や`WIN`を事実とし、中間的な見た目の変化は代理報酬でしかない。見た目を大きく変えるだけの行動を高得点候補としない。
- 異常の局所隔離：1ゲームの不正Frame、GAME_OVER、予算超過が全ゲームの時間・評価を失わせないよう、公式Runnerで許される範囲に収める。
- 観測上の違和感はログに残すが、**知覚できないhidden stateをAPI以外から取得しない**。

### 3.3 まず要求する最小完成形

以下が揃うまで「提出実装完成」と報告するな。

1. 少なくとも複数の異なる公開ゲームで、合法Actionを実際に連続発行する。
2. 1Actionにつき`env.step`一度、Action6のx/y、RESET、GAME_OVERを適切に処理する。
3. 対象・関係・操作結果に基づく計画または探査方針が更新され、無変化連打だけで終わらない。
4. `levels_completed`とAction数を取れ、何もクリアできない場合も原因を分類して、次の改良を選べる。
5. 公開ゲーム全数と、予算/依存/秘密・一般化について本番向けの合格試験が通る。**高得点を保証できないなら未達を正確に記す。**

## 4. 短期から高性能へ：開発の実行順

### Sprint 0：当日すぐ実施

- `57527856`のKaggle状態を再取得。`PENDING`/`ERROR`/数値scoreを確定し、枠・Notebook版を固定。
- `接続/ARC3提出agent.py`を含むAgent/境界/Runnerのstep所有者を決定。1Action=1step、起動時Frame、GameOver、action6、初動Actionのtargeted tests。
- 現行HDSの合法探索アダプタを追加し、HOLDで即終了する機構を分離。複数公開ゲームでの連続作用を実証。
- 既存の公開ゲーム実行器で`games_started, levels_completed, games_won, total_actions, terminal_reasons`を一度全数計測。学習未実証はそのまま記録。

### Sprint 1：まず公式スコアを動かす

- 低リスク操作探索・新奇性/反復検知・目的兆候と再計画を付加し、公開ゲームで最低限の実動作改善を測定。
- 旧Notebook生成器を修正し、**機能するAgent**を再現可能なhashで梱包。9h制限、インターネット無効、オフラインwheel、Gateway起動、初回Action待ちを確認。
- Kaggleの既存の正規操作方法でSave&RunAll→Competition Rerunへ。HOLDだけのダミーによって正常採点枠を浪費しない。現行の残枠に従い実施。
- 公式数値score、Notebook版、submission ID、errorDetails、比較値を固定。エラーなら「4.3」の修復ループ。正常0.00は低実力としてSprint 2へ。

### Sprint 2：汎用攻略能力を増強

- 全25ゲームの失敗署名を集約：①動かない/不正、②操作意味不明、③操作は効くが目標不明、④目標候補はあるが探索失敗、⑤レベル突破するが操作効率悪化、⑥時間・API環境。
- 期待RHAE増分の最も大きい一分類を選び、既存処理資産（連結・形状・位置・色・線・反転・周期等）から最小機構を接続。どう効くかを公開ゲーム横断で検証。
- 世界モデル/行動予測/進捗信号/複合条件/階層的計画を必要条件から増強。人工的な汎用性の宣言はせず**未見ゲームで結果を見る**。
- クリアレベルの行動数は人間基準が分かる場合のみRHAEとして計算。分からなければ行動数・カバレッジ・同一環境のproxyを区別。
- 変化した一般規則の学習・更新を固定seed条件でA/B/C/D比較し、スコア・モデル更新・Action変更を追跡。

### Sprint 3：最善版を競技へ反復投入

- 全ゲームの平均改善か、未突破ゲームへの横断的突破が確認できた改良から順にNotebook候補化。
- 公式採点の実残枠/締切に合わせて、**一日に正常得点枠を使うなら最善の候補**を提出。ERRORは採点成立として終了せず、再送可能な限り修正・同日提出を継続。
- 他の合法な公開実装・探索技術・モデルが高スコアへ必要なら現場に取り込み、HDS貢献をA/Bで切り分ける。ライセンス/9h/秘密・ネット禁止は維持。
- Kaggle首位・本人得点・差を毎回更新。今の変化幅で首位に届かないなら「性能向上」と「優勝ペース」を区別し、**解法系統自体の転換**も計画する。
- 締切前にNotebookの良い2版、Kaggle最終選択の操作・受理を確認し、選ばれた版を証拠に残す。

## 5. 手元実行とKaggle運用の具体手順

### 5.1 Windowsが主環境

- リポREADME/`接続/開発環境.md`のPython/uv/SDK固定値を**現場で再確認**。過去の観測ではPython 3.12.10、uv 0.12.19、arc-agi 0.9.8、arcengine 0.9.3。Windows上でCodexから使える通常のシェルとKaggle CLIを優先。WSL必須と推測しない。
- 公開の現行依存はlockで固定し、追加ライブラリは本番に同梱可能か確認。`PYTHONUTF8=1`等の文字コード対策が必要なら狭く適用。
- まずrepoの正規経路を使う。以下は**例**であり、実在する現在版のパス/引数と照合してから実行する。

```powershell
python -m uv sync --locked
python -m uv run --locked python 道具/開発環境確認.py --offline-game
python -m uv run --locked python -m pytest 検証/test_ARC3提出物構築.py -q
python -m uv run --locked python 道具/ARC3提出物構築.py --owner tecchannn --output-dir 出力/ARC3-RUN-003-<unique>
```

`<unique>`は実際の一意ディレクトリ名に置換。**既存の出力を上書きしない**。pytestやRuffの既存ターゲットはrepoの検査指示に従う。検証対象のHOLD専用assertが実動作仕様に矛盾する場合は、過去基線を別テストで保存しつつ、現行合格条件へ試験を書き換える。

### 5.2 Kaggle公式提出まで

- 現行Kaggle CLIのusageと競技設定を確認。既存記録では初回`--file`不足で400を受け、追加提出として受付されなかった。修復済みの送信形は次。**必ず現在のNotebook slug/version/実際のbasenameに合わせて変更すること**。

```powershell
python -m uv run --locked kaggle kernels push --path 出力/ARC3-RUN-003-<unique>
python -m uv run --locked kaggle kernels status tecchannn/<new-slug>
python -m uv run --locked kaggle competitions submit arc-prize-2026-arc-agi-3 --file submission.parquet --kernel tecchannn/<new-slug> --version <verified-version> --message "ARC3-RUN-003 scored-agent <sha>"
```

- 競技Notebookの`KAGGLE_IS_COMPETITION_RERUN`等のフラグは現SDKと突き合わせる。現行コードにはGateway`curl`の長いリトライ、オフラインwheel、`ARC-AGI-3-Agents`のコピー、生成したmy_agent注入がある。初動タイムアウト・使用可能時間を減らす固定リトライ・意図しない認証情報の混入を監査。
- `COMPLETE`のNotebook commitは競技採点そのものではない。competition submissionの**IDと数値score**を取得。出力Parquetのdummyスコアを再表示するだけなら失敗と扱う。
- `GameAction`の`step()`呼出元、Action送信数、各ゲームの`levels_completed`を分離記録し、公式スコアゼロの理由を推定で断定しない。
- CPU9h/GPU9h、Internet無効、Kaggleの競技専用GPU提供の実在を確認。**GPUが使えるはずという期待だけでNotebook設計を固定しない**。

### 5.3 Submission Retry Loop（絶対に省略しない）

```text
SUBMIT_CANDIDATE:
    source hash / package / Notebook version / local acceptanceを記録
    最新limits, 自分の正式提出履歴, 競技期限を照会
    送信可能なら Competition Rerun を実施
    submission_id とAPI応答を記録

POLL:
    PENDING/RUNNING -> 同ID追跡。別ローカル作業継続。正常待ち中の重複送信なし
    数値score＋errorDetailsなしの終端 -> SCORED_ACCEPTED（0.00含む）
       -> 前回比較、当日有効枠状態の記録、次候補開発
    ERROR/timeout/数値scoreなしの終端 -> TERMINAL_ERROR_NOT_SCORED
       -> errorDetails/log/code/環境から原因分類
       -> 原因に沿った局所修正、targeted test、Notebook再生成
       -> 最新limits/受付可否を照会
       -> 送信可能なら**同日何回目でも再送**、不可なら可となる時点まで開発
    status/score/API不整合 -> UNVERIFIED
       -> 公式履歴/詳細画面/limitsを再照会。勝手に成功・失敗と確定しない
```

- **同日ERRORの再提出回数に人工的な固定上限を設けるな。** ただし実API枠・時間・リソース・期限、重複同一エラーの解消見込は実際に制御する。根本原因の修正なくAPIへ無限連打することは禁止。
- 最終的な1日1件の正常採点上限・最終2選択は守る。数値0.00の正常採点は有効な提出として枠を消費するから、再提出できないものとして次枠用の能力改善を続ける。
- あるエラーがKaggle側障害の可能性を持つ場合、Notebookの`startup/import/first-action/gameplay/grader`のうち観測できるどこまで通ったか分類。公開Discussionだけで確定しない。自分のログ/APIの裏づけとともに再試行判断する。

## 6. 監査テスト：形式から能力へ

### 6.1 公式SDK境界

- `is_done`に初期ダミー、実`NOT_PLAYED`、実`NOT_FINISHED`、GAME_OVER、WINを渡し、ステップが必要なのに停止しないこと。
- Action1..7/RESETの合法性、`available_actions`更新、ACTION6 x/y範囲と候補対象、GameAction Enum引数リーク、古い観測指紋拒否。
- 操作を実際に送る関数が1箇所だけであり、1リクエストに対するstep回数が1であること。無効Actionと二重Actionがゼロであること。
- Runnerの本番状態では同じ環境を二度`make`しないこと、RESETをフルリプレイの代用にしないこと。
- gateway timeoutやNone frame、1ゲーム失敗、所定Action予算終了が全25ゲーム/Notebookの無関係範囲まで破壊しないこと。

### 6.2 学習・攻略

- 少なくとも複数の公開ゲームで、Action前後で観測・仮説・計画が変わることをログで示す。
- 一度無効と分かった操作候補を反証によって降格し、次の別状況で行動順が変わること。
- 同一条件で固定seed・予算・公開ゲームを走らせ、全数のレベル到達・ゲームクリア・Action数を出す。ゲーム間で攻略IDハードコードがないこと。
- A/B/C/Dで状態hash/決定/効果の変化を示す。比較不可・未実証はそう明記。
- `RHAE`と称する場合、人間基準と公式の集約式・完成レベル・1.15 capが一致すること。人間基準が無ければproxyと明記。

### 6.3 本番受入

- Notebook SHA・agent SHA・バンドル内manifest・依存lock・データ版一致、Internet無効、機密情報混入なし、9h完走、NotebookのPrivate設定、competition source紐付け。
- `SAVE & RUN ALL`、`competition submit API`、`submission pending`、`scored`の各状態を別々に検査。
- `ERROR`に遭遇したら原因に対応した修復記録と実残枠照会。合法なら**同日再提出**。`SCORED_ACCEPTED`に至るまで再試行を続ける。
- 正常`0.00`を「再提出可能なエラー」と取り違えない。`0.00`なら性能改良の次スプリントへ。

## 7. 優勝ペースの監視と戦略転換条件

各公式数値版ごとに次を出す。

```text
現時点/JST：
正式submitted version・数値score：
前回スコア→今回スコア→差分：
最新公表首位→自分との差：
公開ゲーム：開始/全25、勝利ゲーム、レベル完了/母数、作用総数、無進捗率：
現在のRHAE天井の主要原因3つ：
本改良のHDS寄与（比較結果）：
正常採点残枠／エラー再提出余地／期限：
次の最短で差分が出る改善タスク：
```

**戦略転換を要求する条件**：

1. 公式数値が連続して上がらず、25ゲームの主要失敗原因が同じなら、機構追加数ではなく**原因モデル・探索方式・学習更新の表現**を再考せよ。
2. 局所ゲームでだけ伸び、未見ゲームへ転移しないならゲーム固有の過適合を疑い、汎用規則抽出やモデル融合へ変更せよ。
3. レベルは突破してもRHAEが低ければ、成功後の行動列を「答え表」にするのではなく、**抽象化した操作因果・状態モデルから効率的に再計画**せよ。
4. 起動・Gateway/実時間が主要原因ならNotebook/Runtimeを直す。世界モデルを触っても0操作障害は直らない。
5. 公開首位との差が10ポイント超など明白に大きい間、微小な局所改善だけを「優勝ペース」に見せるな。首位への到達可能性を見積もり、必要なら許諾のある公開モデルや別原理の探索を実験し、HDSへの接続を検討せよ。

**試験PASS=品質管理、レベル突破=局所能力、公式RHAE=競争能力、学習の対照実験=Learning Machineの実証**。いずれも他の代わりにはならない。

## 8. 成果の採否・Git・権限・非開示

- 作業チケットは「目的、具体的原因、対象ファイル、変更範囲、保護条件、反証可能な受入、実験証拠、採否、次作業」を1件単位で残す。タスクの終了で全体運転を止めない。
- Git mainは安全な通常の変更・検査を前提とし、誰かの未コミット差分を上書きしない。force push、history rewrite、旧バージョン消去、旧結果の「最新値」への書換えは禁止。採用しない案の差分もログで追跡可能にする。
- `AGENTS.md`、`制御/現在状態.json`、HDS Native/原理正本等の保護対象を無断変更しない。Kernel改造が必要ならまずDomain Adapterの不足を証拠で示し、不可避ならOwnerの別承認を求める。
- `運用/ARC3文書正本.md`を更新する場合、受領した3ファイルのSHA256・新しい保存先・適用日を記し、v1/v2と旧E5ログを全て保持。保護規則との矛盾が見つかれば範囲を示して停止。
- Secret/API key/認証Cookie、非公開評価正解、公式ゲーム内部state、HDS Nativeの秘密実装をNotebook・repo・公開ログに混入させない。
- 公式のオープンソース/賞資格条項により非開示原則と衝突する場合、**勝手に公開・非開示方針変更しない**。公開可能なDomain Adapter版の資格を規則と対照し、不可ならOwnerに選択を求める。その判断待ちは通常の性能開発を止める理由ではない。

## 9. 定期的な報告、真の中断条件、最終到達

### 9.1 1チケットごとの記録

```text
ARC3-RUN-003 / Ticket ID：
Owner目的・保持条件の再確認：
git SHA／変更ファイル／作業ツリー：
直前の客観的失敗現象と原因仮説：
採用した変更と反証試験：
公開25ゲーム previous / current / delta：
学習系統・記憶の before / after・未見転移：
Notebook／Kaggle実績：status, errorDetails, score, submission_id, quotas
競争首位との差と本変更の寄与：
PASS／FAIL／未観測・不採用理由：
次のチケット（通常は自動着手）：
```

### 9.2 仕事を止めてよい条件

- Ownerから停止命令。
- 正規のログイン/資格情報/操作権限を得られず、依頼範囲で可能な代案がない。
- `AGENTS.md`、競技規則、保護された状態・秘密保持に具体的な違反が生じ、権限内で回避不能。
- 高危険・不可逆な破壊を避けられず、Ownerの判断が不可欠。
- 提出締切・実際の実行資源の終了（続きの状態/再開点保存後）。

以下は停止条件ではない：`HOLD`、初回/再提出の`ERROR`、スコア`0.00`、Notebook `COMPLETE`、1タスクの成功/失敗、Gitへの記録、翌日提出枠待ち。後者では**ローカルの能力開発を続行**する。

### 9.3 最終納品

1. v3で実行可能なARC3 Agent、HDS汎用記憶/因果/計画接続、Notebook提出パッケージ、検証手順と実際のGit SHA。
2. 公開25ゲーム全数のレベル攻略/Action効率と失敗分類、同条件改善の証拠。
3. Learning MachineのA/B/C/D・状態差分・別条件への転移結果。実証できなかったなら未実証と記載。
4. Kaggle公式提出履歴（特に`57527856`の確定結果とv3各提出）、**公式の数値score、status、エラー再提出の履歴、最善版**。
5. 締切前の最終2候補選定、現時点の順位・首位差、賞資格の非開示整合性。

**最後に：Codexは文書を守っているだけでは終わらない。実動作・学習・攻略・公式採点・改善という目的の因果連鎖を完成させよ。現有資産を使い、実測で不成立なら構造から改め、競技期限まで優勝を目指して継続すること。**

