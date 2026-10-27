# ARC3 P1-3 HDS公開遷移入力 runtime比較

- 作成時刻: 2026-10-24T09:41:47Z
- 条件: public dev、同一split manifest／seed 31／同一探索方針／同じ12合法Action。
- 以前: HDS更新 34.472319s、全体 35.390s。
- 現在: HDS更新 0.639907s、全体 1.262s。
- 差分: HDS更新 -33.832412s (-98.144%)、全体 -34.128s (-96.434%)。HDS更新は 53.87倍速。
- 3独立game smoke: 3/3で非RESET合法Action 2回以上、合計12合法作用、違法0。80 SDK-action stress: 78非RESET合法作用、RESET 2回、違法0、elapsed 38.456s。win／level完了は0であり、攻略成功の証拠ではない。
- targeted検証: 29 passed、3 subtests passed。展開したbundleをimportし、公式offline runnerでネットワーク呼出を遮断して行動まで確認。
- package: `d00ab4af0613a4949e13a886fbaf12a5b61c868c3aaaac42320ba38d1268301e`（source bundle SHA256）。私有事前記憶は含めていない。ライセンス・出所・ID非依存の実行経路を確認するまで追加しない。Kaggle提出もしていない。

## 判定

HDSの各遷移更新に渡す構造化入力を、公開状態要約を決定的JSON文字列にまとめた少数特徴へ絞る変更を採用する。作用前後の公開状態、Action番号、レベル増分を記録し、`因果確定=false`を維持する。同一12作用条件でruntimeを大幅に短縮した。P1-3はbundle内の事前記憶統合と完全な競技Rerun、能力成果について未成立のため全体PASSとはしない。

## 証拠完全性

固定名の`P1-3_MyAgent_local_smoke.json`は、今回の前半で4-action測定により上書きされ、直前にあった3ゲーム×16-action JSONは復元できなかった。過去のセッション要約に48作用・120.642秒との記載はあるが、原JSONとhashが無いため受入根拠に使っていない。検証scriptはUTC時刻付き新規ファイルをexclusive-createし、再上書きを防止する。

詳細JSON: `運用/証拠/ARC26-UNIFIED/P1-3_HDS_transition_compact_benchmark_20261024.json`。
