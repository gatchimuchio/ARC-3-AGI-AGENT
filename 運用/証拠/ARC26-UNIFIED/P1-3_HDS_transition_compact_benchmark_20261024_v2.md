# ARC3 P1-3 HDS公開遷移入力 runtime比較（人口ラベル訂正版）

訂正対象: `P1-3_HDS_transition_compact_benchmark_20261024.md` と、この実験で参照した先行smoke JSON。

## 観測母集団

プロジェクトv3は`入力/`を公開25ゲームの評価資産と説明する。実データの`metadata.json`は25件あり、train/dev split項目は無い。先行記録の「public dev partition」と「split_seed」は不正確で、選択順seedをsplitと誤記していた。以後は「プロジェクト記載の公開25ゲーム環境群。個別metadataにtrain/dev区分なし」と表記する。訂正後の3ゲームsmoke: `運用/証拠/ARC26-UNIFIED/P1-3_MyAgent_local_smoke_20261024T094358Z.json`。

## HDS runtime比較

- previous: 34.472319s HDS更新、35.390s全体。
- current: 0.639907s HDS更新、1.262s全体。
- delta: -33.832412s (-98.144%)、全体 -34.128s (-96.434%)。同じ25件metadata manifest、選択順seed 20261022、Action seed 31、探索方針、12合法Action。
- 訂正後の3独立エピソード: 3/3で非RESET合法Action 2回以上、違法0。
- 80-SDK-action stress: 78非RESET合法Action、2 RESET、違法0、38.456s。winとlevel完了は0。
- targeted verification: 29 passed, 3 subtests passed。

事前記憶`記憶/事前記憶/v0.4`はpackageへ含めていない。READMEとmanifestに公開25ゲーム由来の記載はあるが、ファイル単位のlicense/provenanceとID非依存の実行経路を確認できていない。ARC3 P1-3はこの資産接続と本番Competition Rerunが未検収のため、全体PASSではない。

直前の固定名smoke出力を上書きした事実と、復元不能な過去16-action証拠の扱いはv1報告の証拠完全性節を参照。訂正済みJSON: `運用/証拠/ARC26-UNIFIED/P1-3_HDS_transition_compact_benchmark_20261024_v2.json`。
