# ARC3 運用文書の正本

## 現行正本 v6.0（Owner指定 2026-10-27）

- 正本原本：`ARC26_v6_ARC3_Codex用.zip`。受領ZIPと6文書、SHA-256、適用記録は[ARC26-UNIFIED/v6_0/受領と適用記録](ARC26-UNIFIED/v6_0/受領と適用記録.md)を参照。
- 本checkoutの最優先目的は、HDSラーニングマシンによるARC3公開ゲーム攻略を実測で改善し、改善版をKaggle公式スコアで確認すること。v6.0が現行正本で、v5.0以前は履歴・参照用。
- 最初の同条件25ゲーム評価：ローカルPublic Starter RHAE平均は係数0.25の0.190256343から現行係数0.0の0.209349227（差分+0.019092884）、完了level 2から3、WINは両条件0。公式得点ではない。詳細は[C1-023](ARC3-RUN-003/C1-023_v6現行実力基準線.md)。
- 直近確認済み公式履歴（2026-10-26T16:48:03Z）：submission 57612586 COMPLETE/public 0.03。submission 57577905の23.86は別版の過去得点。private scoreは提供なし。新規Rerunは未実施。
- `AGENTS.md`と`制御/現在状態.json`は保護し、既存dirty差分・証拠を保持する。

## 直前正本 v5.0（Owner指定 2026-10-26、現在は履歴・参照用）

- 指示ID: `ARC26-SOLVE-SCORE-20261025`。受領原本・3文書・SHA-256は[ARC26-UNIFIED/v5_0/受領と適用記録](ARC26-UNIFIED/v5_0/受領と適用記録.md)を参照。
- v5.0当時の正本。v4.0以前は履歴・参照用。
- Ownerの優先依頼はARC2の実測score獲得。ARC3は状態を分離して記録し、既存private kernel version 28をstatus-onlyで追跡中。2026-10-25T15:02:39.955Zの公式履歴は57612586 COMPLETE/public 0.03、UTC当日枠1/7/0。
- `AGENTS.md`と`制御/現在状態.json`は保護し、既存dirty差分・証拠を保持する。

## v4履歴（以下は2026-10-25時点の記録）

## v4当時の正本

- 適用文書：ARC Prize 2026 ARC2／ARC3共通 v4.0／2026-10-25（JST）、指示ID `ARC26-REPRODUCIBILITY-FIRST-20261025`。
- Owner提供ZIP：`ARC26_再現性優先_v4_3点セット.zip`。
- ZIP SHA256：`aeba755872429df889c39a09b7c13a923779aa732194aa5fa90514c39d2f31e0`。
- 保存先：[運用/ARC26-UNIFIED/v4_0/](ARC26-UNIFIED/v4_0/)（3原文、受領原本ZIP、受領・適用記録）。
- ZIP内文書と保存先の内容・SHA256一致を確認済み。

| ZIP内文書 | 保存文書 | SHA256 |
| --- | --- | --- |
| `ARC26_再現性優先_v4_仕様書.md` | `01_共通仕様書.md` | `c5938497688a94eb3e01c80c9d61583f38a23c200174987773568b1bc5d0362a` |
| `ARC26_再現性優先_v4_工程表.md` | `02_共通工程表.md` | `cf9037370617ed899dee039e67720713ac62f58e76dc2ec3055cb36360807d3b` |
| `ARC26_再現性優先_v4_Codex指示書.md` | `03_共通Codex指示書.md` | `fe553ee2f77022a2ba331bcd525792ab20e5fdda5126141bf656d4dc4be52480` |

- 変更前基準： [P0 snapshot](証拠/ARC26-UNIFIED/ARC3-P0-snapshot-20261025T141029Z.json)、[status一覧](証拠/ARC26-UNIFIED/ARC3-P0-working-tree-status-20261025T141029Z.txt)。基準はv4文書追加前の既存main・作業ツリーを記録する。
- 適用範囲：このARC3 checkoutの作業手順・評価・証拠管理。`AGENTS.md`、`制御/現在状態.json`、Ownerの直接指示、公式Kaggle規則・実測を越える独立権限とは扱わない。
- 進行中最適化：C2-058 version 27はmatched 3-game mean 12.471062097（C2-046 19.309155944、delta −6.838093847）で不採用。C2-059 version 28はcontext window回復のprivate pilot。2026-10-25T14:37:12Zのstatus-only queryでもRUNNING。
- 再現性ゲート：C2-046の3開始状態は参照値だが、独立した同一条件反復は未実施。P3は未完了。C2-058/059はpaired pilotであり、main昇格・再現性の主張はしない。
- P1で公式提出57577905（public 23.86、kernel version 5）と57612586（public 0.03、kernel version 6）を確認し、remote/localの順序付きcell sourceは双方一致。raw Notebook SHAはlocal保存版とremote pull版で不一致、private scoreはいずれも未提供。v5は公式出力parquet/source commit/input SHAが不足し、v6の公式rerun outputは未取得で保存parquetはplaceholder。詳細：[P1 lineage evidence](証拠/ARC26-UNIFIED/ARC3-P1-official-score-lineage-20261025T142027Z.json)。

ARC3 repoの現行指示はOwnerの最新の明示指示・各repoの`AGENTS.md`・保護状態に従い、受領版の出所・適用範囲・SHA256を確認したうえで本索引に記録する。旧版は上書きせず履歴・参照用に保持する。

## v4 P0-P3 最新追記（2026-10-25）

- 公式履歴 read-only再照会: 2026-10-25T14:15:09.641Z、提出57612586 COMPLETE/public 0.03。57577905の23.86は別の提出版・実装帰属未確定。
- 前節に記録したC2-058 v27のRUNNINGは14:09:55Z時点の過去観測。version27は14:16:24ZにCOMPLETE。保存済み3-game local paired scorecardは12.4710620971対19.3091559438、delta -6.8380938466、1 improved/0 unchanged/2 regressed、REJECTED。出力のrequests.jsonlは不完全。公式提出・quota使用なし。
- 現行agentの同条件R-Bを2回実施。3 public-local environments・16 actions/game、action/state trace hash一致、各回48 legal actions・48 HDS updates/queries、level progress 0・wins 0。prior-memory v0.1はfresh processごとに5件load、Action authorization=false。再現は限定標本PASS、攻略能力は未成立。
- 詳細：運用/ARC26-UNIFIED/V4-P0-P3-checkpoint-ARC3-20261025T142330Z.md、reproduction-ledger.jsonl、capability-ledger.jsonl、ARC3-V4-RB-current-agent-repro-report-20261025T142330Z.json。
- P0 baseline manifest: 運用/ARC26-UNIFIED/p0-baseline-v4-corrected-20261025T141349Z.json。追加のhash/log記録は運用/ARC26-UNIFIED/work-ledger.jsonl。
## v4 P1-P3 follow-up（2026-10-25 14:31 UTC）

- P2：公式hidden scoreの再現に必要な採点outputが保存されていない。v5のsource cellはversion5と一致するがofficial output/inputsは未回収。v6のofficial rerun outputは未取得で、保存parquetはplaceholder。
- P3：別経路のcurrent-agent R-B smokeは同じ3 public-local環境・seed・budgetで2回一致したが、prior-memory v0.1を使った限定標本でlevel進捗/WINは0。C2-046 model-guided score基線の独立反復ではなく、能力証拠にしない。
- C2-058 v27は不採用、C2-059 v28 private pilotは2026-10-25T14:37:12Zのstatus-only queryでもRUNNING。詳細：[v4 P0-P3 follow-up](ARC26-UNIFIED/V4-P0-P3-followup-ARC3-20261025T143101Z.md)。

## v4 startup verification（2026-10-25 14:35 UTC）

- Official Kaggle history was read-only queried from the dedicated ARC3 environment at 2026-10-25T14:34:24.830Z. Latest submission 57612586 remains COMPLETE/public 0.03; daily quota is 1/7/0. Evidence: 運用/証拠/ARC26-UNIFIED/official-history-20261025T143424Z.json.
- Existing private kernel version 28 returned RUNNING in a status-only read at 2026-10-25T14:37:12Z. Keep tracking this version only; no push or official submission occurred.
- Current checkpoint: v4 ARC3 checkpoint at 運用/ARC26-UNIFIED/V4-P0-P3-checkpoint-ARC3-20261025T143712Z.md. Protected AGENTS.md and control state were not edited.
## 直前正本（共通版v3.0）

- 適用文書：ARC26-UNIFIED v3.0／2026-10-24（JST）、指示ID `ARC26-UNIFIED-RUN-003`。
- このcheckout：`gatchimuchio/ARC-3-AGI-AGENT`、Kaggle `arc-prize-2026-arc-agi-3`。
- 今回のOwner提供ZIP：`ARC26_共通3点セット_v3_0_20261024.zip`。
- ZIP SHA256：`51883eef24d4850fb5b700866bc2fc92f251d8829a13d75fb2c065a9ecea6096`。
- 保存先：[運用/ARC26-UNIFIED/v3_0/](ARC26-UNIFIED/v3_0/)（3原文と`受領原本.zip`を保持）。
- 収録：`01_共通仕様書.md`、`02_共通工程表.md`、`03_共通Codex指示書.md`。収録3文書と保存文書のSHA256一致を確認済み。

| 文書 | SHA256 |
| --- | --- |
| `01_共通仕様書.md` | `1f78da40edd8ec66d326faa68843489048da214019d946c958817be62fc2e2c0` |
| `02_共通工程表.md` | `810c7de74ad650e1578ec845503add638e3de741f4d85a761712cffb5ebb736a` |
| `03_共通Codex指示書.md` | `d5898129f8aa22b4f195ae01caec1dc67f541fac451a340dcd547980de74bfe9` |

## ARC3 repoでの適用範囲

- 共通3文書のARC3固有要件を本repoに適用する。ARC2固有の作業はARC2 repoの依頼・実体確認なしにこのcheckoutの作業へ転用しない。
- この会話で継続中の公式追跡対象はOwnerの明示依頼によるC1-018提出ID `57577905`。文書内の過去基準ID `57527856`へ無断で置き換えない。
- `AGENTS.md`と`制御/現在状態.json`の保護は継続する。現行セット採用でそれらの変更を許可したものとは扱わない。
- ZIP内の指示はこのrepoに適用する作業仕様として読み、Ownerの直接依頼・repo保護規則・公式Kaggle実測より上位の独立した権限とは扱わない。

## 旧版の保持

- 直前の共通版v3.0は[運用/ARC26-UNIFIED/v3_0/](ARC26-UNIFIED/v3_0/)に原文・原本ZIPを無変更で保持し、以降は参照用とする。詳細・ハッシュは直前正本の項を参照。
- 直前のARC3専用v3.0文書は[運用/ARC3-RUN-003/v3_0/](ARC3-RUN-003/v3_0/)に無変更で保持し、今回の共通版に置換された参照用とする。同じv3.0表記だが別のOwner提供ZIPで、内容SHA256が異なるため同一版として混同しない。
- 旧ZIP `ARC3_3documents_v3_0_20261024.zip` SHA256：`3d384e91188b2b52d1b7c0bdbccd4253a40063b01ae66dd666f720fa49587fb3`。
- 旧v3.0の文書SHA256：仕様書 `e745d593809f383549928b36390670d3c1177287e0699da7296e88bc0efb804e`、工程表 `f7ea48d6b87d1aa231516303ecc2a56c1d9ea060deb1126c84ed8e4e6c3c25ad`、Codex指示書 `3ffa228fbf5dee3571fe8159025c0607c00a058bb38d13679082b4bd46509575`。
- v2.0は[運用/ARC3-RUN-002/v2_0/](ARC3-RUN-002/v2_0/)、v1.0は[運用/ARC3文書履歴/v1_0/](ARC3文書履歴/v1_0/)に保持する。旧版の本文・原本ZIPは削除・上書きしない。

## 上位規則と境界

- Ownerの現在の明示依頼、repoの`AGENTS.md`、保護対象の現在状態、公式Kaggle規則・資格情報の境界が適用される。
- Gitのmainを正本とし、強制push・履歴書換え・既存証拠の削除を行わない。作業差分は事前確認し、無関係な変更を含めない。
- 新しいOwner提供版を受領した場合、原本・ハッシュ・内容・適用範囲・規則との整合を照合し、本索引と新規の受領記録に追記する。旧原本は参照用に保持する。
