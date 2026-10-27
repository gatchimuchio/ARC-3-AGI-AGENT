# C2-008 指示書：同一盤面で無変化だったActionの再選択抑制

- 指示ID: `ARC3-RUN-002-C2-008`
- 版: 1.0／2026-10-23（JST）
- 対象: 観測駆動探索Actionの公開観測条件付き選択
- 前回基準: C2-003候補、UCB探索係数0.8、no-op罰-1.0
- 根拠: C2-007 holdout seed73でAction4選択275→311、no-op7→26、同一盤面での再実行2→13となり、no-op総数137→149。seed31もAction4 no-opが3→9。

## 仮説

離散Action 1–5,7が同じ公開盤面に対して可視変化もlevel進行も起こさなかった場合、そのActionを同じ公開盤面で再選択する優先度を下げると、同じ状態での反復no-opを減らせる。別の合法Actionがあるときだけ適用し、候補が尽きた場合は既存選択へ戻すことで探索停止を避ける。

## 許可する範囲

- `接続/観測駆動探索Action.py` に無効化可能な実験flagを加え、公開盤面tupleと離散Action番号から直前のno-opを記録する。
- `検証/ARC3探索Actionローカル評価.py` にflagを渡す引数と出力条件を追加する。
- `検証/test_観測駆動探索Action.py` に、同盤面で別合法Actionへ移る、代替がなければ従来選択へ戻る、盤面が変わればActionを再評価するテストを加える。
- dev受入後のみ、開発対象外の同じ20 holdout環境をseed 7/31/73で固定評価する。

## 保持条件

- UCB式、全報酬係数、Action初手順、ACTION6の座標・色選択は変更しない。ACTION6は座標単位の既存未試行管理を使い、この実験の離散Action抑制対象から除く。
- 直近の前後公開観測だけから無変化を認定する。hidden state、API外メタデータ、game/level ID、filename、hash、trajectoryを使わない。
- 可視盤面が違えば以前のno-op記録を選択除外に使わない。
- 全合法Actionが候補除外になるときは除外を解除して既存方針へ戻し、人工的なHOLDを作らない。
- HDS/HOLD、SDK RESET、WIN停止、Action要求80上限、違法Action0、duplicate step0を保持する。
- 既定flagは評価完了までOFF。受入前にNotebook・提出kernelへ反映しない。
- `AGENTS.md`、`制御/現在状態.json`、正本ポインタ、v2.0文書、v1.0履歴、HDS v0.4.2を変更しない。

## 検証と事前受入条件

1. 同一の公開5件dev splitをseed 7/31/73、80要求上限、GAME_OVER後RESETありでC2-003版と比較し、各seedで開始盤面5/5一致を確認する。
2. devは各seedで完了levelを基準未満にせず、全seed合計no-opが減り、少なくとも2 seedでno-opが減ること。policy holdは基準を上回らず、違法Action・duplicateは0を維持する。
3. 条件未達ならholdoutを実行せず、flag既定OFFのまま不採用とする。
4. dev受入時はflagを固定して20 holdoutを各seed一度実行する。各seedで完了levelを下回らず、合計no-opが減り、いずれのseedでもno-opを増やさず、policy hold・違法Action・duplicateを増やさない場合のみ採用を検討する。
5. 局所評価から公式scoreやhidden環境性能を推定しない。採用時のみ候補再構築・通常Notebook実行・提出枠確認へ進む。

## 終了条件

previous/current/delta、同一盤面反復・no-opをAction群別に記録し、出力SHA-256とテスト結果を残す。採否を確定し、次の診断へ進む。
