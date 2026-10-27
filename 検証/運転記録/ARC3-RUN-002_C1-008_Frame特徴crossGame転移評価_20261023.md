# ARC3-RUN-002 C1-008 Frame特徴cross-game転移開発評価

- 実施日: 2026-10-23 JST
- 指示: [C1-008指示書 v1.1](../../運用/ARC3-RUN-002/C1-008_Frame特徴crossGame転移開発評価.md)
- 判定: **事前の転移受入条件FAIL。Frame HDSは共通coverageでAction-only HDSまたは多数派を上回らず、新規盤面は全foldで予測なし。holdout/runtime接続は不採用。**
- 範囲: 固定dev split先頭5公開環境、environment seed 31、policy seed 7/31/73、各最大80要求。5-fold leave-one-environment-out。

## 実行条件

環境ごとにAction応答を一度収集し、各foldで対象環境の全eligibleサンプルを評価した。残る4環境からは、各環境の時系列全体に均等配置した15サンプルずつを抽出し、最大60件でAction-only HDS、Frame条件HDS、Action別多数派を学習した。Frame条件はC1-006で固定した直前応答の複数Frame・中間grid差分・一時差分cellの3真偽値を使う。各policy seedで5環境の公開開始状態は5/5一致し、389件を各5 foldで一度ずつ評価した。

全eligible訓練行を使う初回試行は約25分経過後もartifact出力前だったため終了した。途中結果は採否に使わず、C1-008指示書をv1.1へ改訂し、各訓練環境15件の均等抽出を固定して全15 foldを完了した。出力内の環境数キー表記を実行後に修正したが、予測指標は変更していない。実行時source SHAは f141596a333185241e04cbe84ccaa741c3f11f6317356f0cf54bf780de15d98d、表示修正後の現行評価器SHAは A6991D364C38F27FD8C5193547453595624F55C5F1626DE3636C588A4AAB5251。

## previous / current / delta

集計は各policy seedの全5foldを合算。各件数は同じheldout sample集合に対するcoverage/正答である。

| 結果 | Action-only HDS previous | Frame HDS current | delta coverage/正答 | 三者共通coverage | Action別多数派 |
|---|---:|---:|---:|---:|---:|
| 可視変化あり | 154/148 | 155/148 | +1 / 0 | 154件、Action-only/Frame/多数派はいずれも148正答 | 1,099/1,125 |
| level進行あり | 834/831 | 855/852 | +21 / +21 | 834件、3条件とも831正答 | 1,122/1,125 |
| 新規盤面あり | 0/0 | 0/0 | 0 / 0 | 0件 | 986/1,105 |

level進行ではFrame HDSがcoverageを21件増やし、追加分は正答した。しかし三者共通coverageの正答数は全seedで同じで、Action別多数派はcoverage 1,125件中1,122件を正答した。可視変化でもFrame特徴が多数派誤りを直した件数は0。新規盤面ではHDSの予測coverageがなかった。したがって、ゲームを跨いだ予測改善は成立していない。

C1-008の受入条件は、三者共通coverage 30件以上に加えて、Frame HDSが共通集合上で両baselineを上回り、少なくとも2 seedで正のdelta、残りも非負であることだった。可視変化・level進行の共通coverageは十分あるがdeltaは全seedで0、新規盤面はcoverageなしのため不成立。Frame特徴をruntimeへ接続せず、追加holdoutも行わない。

## 証拠と検証

- 対象公開環境入力50ファイルのcontent-set SHA-256: d40c652dfffda990a1a32c65da3d873a36bb9c4b6bd06598704596af3c2ead79。
- 実行時transfer evaluator SHA-256: f141596a333185241e04cbe84ccaa741c3f11f6317356f0cf54bf780de15d98d。修正後のsource/test SHA-256: A6991D364C38F27FD8C5193547453595624F55C5F1626DE3636C588A4AAB5251 / FDF8D93BD42F7209B1C49DD6053F1FC8F51A375D1414A7BF3588C1C6C3975408。
- 匿名aggregate 出力/ARC3-RUN-002-local/C1-008-frame-cross-game-dev-summary.json SHA-256: E294CC92EC5763A24818B3B2B012C5EE6604C69A68221DBB5E6D946B59686881。
- cross-game分離test、C1-006 feature test、境界/HDS shadow suite: 23 passed、20 subtests passed。Ruff check/format、compileall、CLI help: PASS。git diff --check: whitespace errorなし（既存CRLF/LF警告）。
- HDS、提出agent/runtime、candidate bundle、Notebook/kernel、AGENTS.md、現在状態.jsonは不変更。Kaggle実行なし。

## 次工程

直前Frame特徴のshadow評価はC1-006〜008で採用根拠なし。次はfeature familyを増やさずFrame枝を閉じ、RUN-002の未解決優先課題をC0/C2/C3運転記録から再選定する。現時点の結果は公開dev内の診断であり、hidden性能や公式scoreは推定しない。
