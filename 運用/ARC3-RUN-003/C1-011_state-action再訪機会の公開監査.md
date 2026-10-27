# ARC3-RUN-003 C1-011：同一公開盤面の既知no-op Action再選択監査

## 選定根拠

- 現行policyのAction回数・報酬はAction番号単位で集約され、公開盤面文脈をキーにしない。`同盤無変化Action回避`は任意flagで、既定runtimeでは無効。
- C2-007でholdout seed73のAction4 no-op反復が2→13、no-op総数が137→149に増加。C2-008の同盤回避ablationはdevのno-op減少条件を満たさず不採用だったが、既知no-op再選択が何件の判断機会を占めたかは未記録。
- C2-020のavailable_actionsは各run内で変化せず、Action集合だけでは状態文脈にならなかった。C2-037のtie-break seed再計算は全seedでlevel差0・GAME_OVER増となり棄却。Action結果の同一盤面への再訪が実際に多いかを先にread-only観測し、状態別UCBなどの次介入に根拠があるか判定する。

## 許可範囲

- `検証/`に隔離されたlive-run監査器とtargeted testsだけを追加する。通常探索policy、提出agent、HDS、candidate bundle、Notebook/kernel、protected filesは変更しない。
- 固定dev split seed `20261022`の5環境、environment seeds `7/31/73`、各最大80 Action、GAME_OVER後RESET有効。保存Action列再生は禁止。
- `ACTION1-5/7`について、同一runで当該公開盤面上の直前Actionが盤面不変・level非進行だったのに、同じ盤面へ戻ったとき再び選ばれた頻度を測定する。ACTION6は座標引数を伴うため分離し、この監査の既知no-op候補から除外する。
- 公開盤面はプロセス内の一時的な照合にのみ使う。出力はseed別aggregateのみとし、game/level ID、盤面、座標、個別run、trajectoryを保存しない。

## C1採用判断

- 次のC2候補を立てるには、15 run全体で「別の合法な離散Actionが存在するのに、同じ盤面で既知no-op Actionを再選択した回数」が10回以上、かつ3 seedsのうち2以上で観測されること。
- 条件未達なら状態別Action memoryの実装を開始せず、C1を閉じる。条件を満たした場合も、限定C2評価の前に別途介入仮説・受入条件を固定する。

## 保持条件・完了証拠

- 選択順、UCB、報酬、探索係数、RNG、legal gate、RESET、停止条件は変更しない。
- 各seedの15-run未満ではなく、固定5環境×各seedの15-run全体を完了する。開始条件の一致、Action数、no-op、GAME_OVER、RESET、illegal、duplicate、HOLDを照合する。
- 入力・source・test・出力SHA256、禁止情報key監査、採否と次工程を追記記録へ保存する。
