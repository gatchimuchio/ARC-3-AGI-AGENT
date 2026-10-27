# C2-065 — 公開遷移の確率的multi-step価値学習

## 問い

HDSの決定的action/outcome ruleが5ゲーム199更新で有効ruleへ至らなかった。公開状態・action・応答の遷移頻度から、未見公開ゲームで使えるmulti-step価値priorを構成できるかを、評価専用の独立層として測る。HDSは別系統として保持し、本実験をHDSの成果とは称さない。

## 固定条件

- 入力はKaggle Public Starterの25公開metadataとSDK観測のみ。game/level ID、frame画像由来の秘密値、正解や固定action列は学習featureに入れない。
- train/devをseed `20261027` で公開環境一覧から決定的に分割。train 5ゲーム×40 Action、devは未見5ゲーム×seeds `7,31,73`、同一開始seed・policy seed・80 Action上限でbaselineとcandidateをpaired比較する。
- state featureはSDK合法Action集合、色種類数bucket、最多色占有率bucketだけ。値モデルはstate-action遷移件数、公開報酬分布、次state分布からDirichlet-smoothed Bellman期待値を反復計算する。更新値を保存し、IDを含まないことを検査する。
- candidateは事前学習value priorと同じholdout内のオンライン更新を使用。baselineは現行観測駆動UCB。両方ともゲームごとに一時方針状態をresetし、holdout間で情報を混ぜない。
- 各pairのSDK開始状態・初期盤面・合法集合一致を確認し、baselineとcandidateのAction traceが変わったpair数を記録する。
- primary metricは公式`EnvironmentScoreCalculator`によるRHAE。secondaryはlevel進行、WIN、no-op、illegal/duplicate/error。dev gateは平均Δscore `>= +0.01`、improvement数がregression数以上、level合計を減らさず、契約error/illegal/duplicateが0。

## 採否

gate未達ならmodelをruntime・Notebookへ接続しない。gate達成時のみ残る未見15公開ゲームを同じpaired条件でholdout確認する。候補が失敗した場合はmemory/RHAE改善として報告しない。

## 再現境界

local public data only、submission・Competition Rerun・quota・Notebook/kernel編集なし。Runner、policy、環境manifest、trained model state hash、条件、aggregate scorecard hashを記録する。実験用modelはscorecardへ状態/hashを保存後に削除し、必要なら同一runnerから再生成する。
