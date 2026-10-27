# C3-001 指示書：GAME_OVER後の公式RESET再試行

- 指示ID: `ARC3-RUN-002-C3-001`
- 版: 1.0／2026-10-23（JST）
- 対象: ARC3提出agentのGAME_OVER後の試行制御
- 前回基準: C2-001探索方針。seed 7/31/73の20 holdoutで探索側は各1/2/1レベル進行、WINは0。探索側GAME_OVERはrandomより1/1/3件多かった。

## 根拠

- 公開Starter `agents/templates/random_agent.py` は `WIN` のみを終了状態とし、`NOT_PLAYED` または `GAME_OVER` では `GameAction.RESET` を送る。
- 公開Starterの `Agent.main()` はAction要求数を `MAX_ACTIONS` で制限する。RESETも通常のstep要求としてaction counterを消費する。
- 公開holdout上の再現で、GAME_OVER時の `available_actions` は `(6,)` だった。`GameAction.RESET` はこの集合に含まれないが、実際の `LocalEnvironmentWrapper.step(RESET)` は `NOT_FINISHED` を返した。
- `arc_agi.scorecard.Scorecard` は同一gameの複数playを保持し、`most_levels_completed` を集計する。再試行は有効な公式ライフサイクル操作である。
- 現行候補は `GAME_OVER` で停止し、RESETを初回 `NOT_PLAYED` に限定しているため、公式Starterの再試行経路を失っている。

## 目的

`GAME_OVER` をゲーム全体の最終完了と誤認せず、公式SDKのRESETを使い、残りAction予算で同じ公開ゲームへ再挑戦できるようにする。`WIN` は停止状態として維持する。

## 許可する範囲

- `接続/ARC3提出agent.py` と `接続/観測駆動探索Action.py` のLifecycle制御。
- `RESET` を探索Actionから区別した `SDKリセット` 出所として記録する。
- RESETは `NOT_PLAYED` 初回または `GAME_OVER` 時だけ許可し、`available_actions` 外でもこの制御Actionだけを例外扱いする。
- GAME_OVER後のRESET応答を受け取ってから新しい観測・合法Action集合を検査し、次の探索Actionを決める。
- 同一game run内の既存探索統計を保ち、RESET自体を探索報酬やHDS根拠にしない。
- 公式Starter契約を反映したローカル比較評価とtargeted testsを追加する。

## 禁止と保持条件

- `available_actions` 外のゲームActionを許可しない。GAME_OVER時に許可するのはSDKのRESETのみ。
- `WIN` 後にRESETを送らない。
- RESETを探索Action・HDS確定Actionとして記録しない。
- game/level ID、ファイル名、hash、保存済みaction trajectoryをruntime分岐に使わない。
- GAME_OVERからの再試行を含め、初期RESET・再試行RESET・ゲームActionを合算して公式Starterの最大Action要求数を越えない。
- HDS v0.4.2、`AGENTS.md`、`制御/現在状態.json`、v2.0正本・旧履歴を変更しない。

## 検証

1. mock SDKで初回RESET、GAME_OVER後RESET、RESET後の再観測、WIN停止、予算境界を確認する。
2. 公式 `LocalEnvironmentWrapper` で実際のGAME_OVER→RESET→NOT_FINISHED遷移を確認する。
3. 同一公開20 holdout・同一environment/action seed・同一80 step要求予算で、停止版と再試行版を比較する。再試行版ではrandom baselineも同じRESET契約を使う。
4. 進行指標は各gameのplay群における最大 `levels_completed` とする。試行数・RESET数・GAME_OVER回数・WIN・Action要求総数・不正Action・二重stepを別々に記録する。
5. 複数seedで、再試行版が停止版の最大到達を下回らず、合法性・要求予算保持条件を満たすことを確認する。追加試験は方針調整に使わない。

## 終了条件

- `GAME_OVER`後RESETが公開SDKに受理され、次の公開観測後にのみ再開する。
- WIN停止、合法Action検査、二重step防止、80要求上限を保つ。
- 同条件のholdout比較で最大levels completedを維持または改善し、再試行によるAction消費・GAME_OVER数も併記する。
- 条件を満たさない場合は候補Notebookを更新せず、原因を記録する。
