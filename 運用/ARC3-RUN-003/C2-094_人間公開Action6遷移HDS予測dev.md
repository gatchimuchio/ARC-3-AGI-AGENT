# C2-094 人間公開 Action 6 遷移の HDS 予測 dev

## 目的

公式人間デモから現行版一致のAction 6遷移だけを取り出し、既存`HDS/学習系統/v0.4.2`と`記憶/事前記憶/v0.4`へ学習入力として与えた。HDSの入力は現行提出agentと同じ境界・結果分類を使い、座標・IDを除いた公開特徴だけにした。これはゲーム得点試験ではなく、未見環境へ遷移分類を転移できるかの事前診断。

## データと条件

- 入力: `magicsword001/arc-agi-3-public-demo-human-testing`、archive SHA-256 `347a4fdba7075babc84b263273122d623fadbe5183b76daa6850534d72039a7c`。
- ミラー340記録のうち、現在の公開環境版と一致する163件/10環境だけを利用。不一致177件/15環境を除外。train/devは環境単位で7/3、C2-093と同じseed `20261027`・同じ分割digest。IDは版照合とsplitにのみ使用し、HDS入力にも保存scorecardにも出さない。
- Action 6遷移の公開特徴: 現行agentと同じ「合法作用数」「色種類数」「最多色占有帯」、Action番号6、引数あり。公開結果ラベルは`可視変化なし`/`盤面変化`/`レベル進行`/`勝利`。クリック座標、盤面配列、自由記述は入力に含めない。
- trainはAction6例のある4環境から各32件、計128件。devはAction6例のある2環境から各100件、計200件。HDS最小支持数3、最大条件数2。dev中のHDS更新なし。
- 各条件を同じ入力で2回学習・照会し、予測要約digestを照合。locked local Python 3.12.10 / `arc-agi==0.9.8` / `arcengine==0.9.3`。

## 結果

| 指標 | 多数派基準線 | HDS＋多数派fallback | 差 |
| --- | ---: | ---: | ---: |
| 未見遷移の正解率 | 91.5% | 91.5% | 0.0pt |
| HDS予測被覆率 | — | 0.0% | — |
| HDS予測のみの正解率 | — | 算出対象0件 | — |

学習128件の結果は「盤面変化」113、「可視変化なし」14、「勝利」1、「レベル進行」0。HDSの学習状態は128/128件で`断定保留`。未見200件も200/200件が`断定保留`で、有効原理からの予測は0件だった。多数派基準線も未見200件中183件が「盤面変化」で当たり、HDSを加えたfallbackは同じ91.5%のまま。2回の予測digestは一致した。

**判定: `REJECT_HDS_PRIOR`。** HDSの被覆率と精度差のgate（被覆率10%以上、fallback精度+5pt以上）を満たさない。進行・勝利例がほぼなく、ラベルも盤面変化に偏っており、ゲームスコアへ有益な遷移則は確認できなかった。このhuman Action 6 priorを提出agent/HDS本番/Notebookへ入れない。公式提出・Competition Rerunなし。

初回実行はローカル環境に公式Starterの`agents.agent`がなく、提出agent全体のimportで停止した。以降は現行agentの2つの純粋なID-free変換だけを検証runner内に写し、agentファイルhashをscorecardに記録した。HDS API、memory、提出agent本体は変更していない。

## 証拠と制約

- scorecard: `運用/証拠/ARC26-UNIFIED/ARC3-C2-094-human-action6-hds-prediction-dev-20261027.json` SHA-256 `5a6ddca2feb5b58e8351955350dc1298bbfabe91cc0ae1527a744d3fae063512`
- 実行器: `検証/ARC3人間公開遷移HDS予測dev.py` SHA-256 `7c8537a11c2d77346d0bcee719d89ac8d5feb788f395658d6d94ce796417da46`
- command: `python 検証/ARC3人間公開遷移HDS予測dev.py --human-archive <reviewed-archive> --expected-archive-sha256 347a4fdba7075babc84b263273122d623fadbe5183b76daa6850534d72039a7c --output 運用/証拠/ARC26-UNIFIED/ARC3-C2-094-human-action6-hds-prediction-dev-20261027.json` (locked Python 3.12.10; per-group limits 32 train / 100 dev; seed 20261027)
- HDS source-tree SHA-256 `a6fbdd20b82b5f0c01a768f0c295f1f0c6ac03835c3942994c117aabdc8c40e7`、提出agent helper参照SHA-256 `b0643f6d6bfff7fa1520a86248d77963ffeff465b9674df2aa62acdd8a20bbba`。
- Kaggle公式記事は342 replaysを報告し、取得したミラーは340記録。差2件は未解決。Kaggle license labelは`other`。抽出HDS状態・人間データはローカルのみとし、提出bundleへ含めない。
- 同データのAction6局所特徴prior（C2-093）も3環境9組でscore delta 0だった。2つの失敗は「人間Action6遷移を追加すれば競技得点が上がる」という主張を支持しない。
