# ARC3-RUN-003 C2-036：公開Action結果後のHDS候補shadow診断

## 指示・対象

- 指示ID：`ARC3-RUN-003-C2-036`（2026-10-24 JST）
- 正本：v3.0／`ARC3-RUN-003`。旧v1/v2は参照用。
- 優先故障：HDSの公開Action応答に対する経験更新が、後続のAction候補照会へ再利用されない。
- 根拠：現行agentは初回公開観測でHDS語彙を照会するが、Action応答を`処理する()`へ渡さず、探索policyの統計だけを更新する。C1-002ではID-free Action結果要約によるHDS更新を確認したものの、Action候補群へ戻る影響は未測定。A0では空HDSの初期候補が公開25環境で0件だった。C2-034/035 model-memory pilotは準備前に終了し、今回の公開HDS故障とは独立。
- 仮説：実行中に得た公開Action結果をID-free要約として同じゲーム専用HDSへ処理し、同じ後続観測で候補を照会すれば、空HDSより候補群が変わる場合がある。

## 許可範囲

- 新規の隔離shadow評価器とそのtargeted tests、匿名aggregate、追記型運転記録。
- 固定dev split seed `20261022`の5公開環境、environment seed `31`、live policy seed `31`、各最大80 Action、GAME_OVER後RESET有効。現行探索policyが各現在観測からactionを選ぶ。保存済みAction列を再生・lookupしない。
- 各環境で独立したlearned HDSとempty-control HDSを用意する。実際の公開Action応答後に限り、learned HDSへAction番号・可視変化有無・level進行有無・新規可視盤面の真偽値を処理する。RESETは学習対象外。
- 同一の次公開観測に両HDSをread-only照会する。候補は比較にだけ使い、Action選択、権限昇格、環境stepへ一切返さない。
- 出力は全環境集計に限り、game/level ID、盤面、色・座標、GUID/hash、trajectory、個別予測値・候補座標は含めない。Action番号ごとの匿名集計は許可する。

## 禁止・保持条件

- 固定Action列、replay lookup、問題ID・盤面・hashによる分岐、正解・hidden/evaluator情報、既知解・成功trajectoryの使用は禁止。
- `接続/ARC3提出agent.py`、candidate v4、HDS v0.4.2、事前記憶v0.4、Notebook/kernel、`AGENTS.md`、`制御/現在状態.json`、正本ポインタを変更しない。
- Kaggle上のupload/run/Rerun/提出を行わない。candidate結果を性能改善・攻略成功・公式scoreと呼ばない。
- HDS入力にgame/level ID、盤面、色値、座標、観測指紋、trajectoryを入れない。全HDS状態は環境間共有しない。
- 候補は常に`実行許可=False`を保ち、照会前後に両HDSの経験台帳が増えないことを確認する。

## 受入・採否

1. 初期状態、legal Action、環境状態変化を公式公開OFFLINE SDKで実測し、live policyが毎stepを選ぶこと。
2. learned HDSの処理呼出数がRESET以外の探索Action応答数に一致し、control HDSの学習呼出が0件であること。
3. 各観測でlearned/controlが同じ盤面・legal Actionを読み取り専用照会し、Action trajectoryがHDS候補出力に依存しないこと。
4. 予測候補集合のprevious/current/deltaを全環境aggregateで比較し、候補の合法性と`実行許可=False`を確認する。候補座標等の個票は保存しない。
5. replay一致、candidate増加、HDS状態更新だけでは改善と認めない。HDS候補が同じならこの接続仮説を棄却し、runtimeへ接続しない。候補差が観測されても次の独立taskで別seed・複数ゲームに再現し、C3条件を満たすまで採用しない。
6. source/input/output SHA、seed、Action数、学習更新・read-only件数、候補数、previous/current/delta、失敗署名、targeted test、採否を記録する。
