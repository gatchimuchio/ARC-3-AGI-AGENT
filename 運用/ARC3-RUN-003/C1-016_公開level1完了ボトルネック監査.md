# ARC3-RUN-003 C1-016：公開level 1完了ボトルネック監査

## 選定根拠

- 現行B1はKaggle `57541830 COMPLETE / public 0.25`。公式scorecardのepisodes取得はできず、ゲーム別の公式原因は未観測。
- C0-001のscore-aligned公開25環境評価では、25環境×3 seedの75 run中、level 1完了8、level 2以降完了0、WIN 0。公開RHAE seed平均は0.194405で、完了depthが最初のlevelに留まる。
- no-op削減やUCB文脈変更のC2-038〜041はlevel進行を増やさず棄却済み。既存係数、seed、同盤面統計を再調整せず、level進行そのものに関係する公開出力を再監査する。

## 目的・許可範囲

- 固定公開環境25件、split seed `20261022`、environment/policy seeds `7/31/73`、最大80 action/run、GAME_OVER後RESETをlive実行し、level 1完了の前後で公開観測可能なaction種類と応答カテゴリの集計差を確認する。
- 観測カテゴリは`no_op / board_change_without_progress / level_progress / game_over`。action種類は`discrete / coordinate`に畳み、特定action番号・色・座標・board・環境/level識別子を選択条件または出力へ含めない。
- 集計はseed別および全体の件数・率のみ。個別run・action列・問題ID・盤面・座標・GUIDは保存しない。
- agent、policy、HDS、事前記憶、Notebook/kernel、保護対象、Kaggle stateは変更しない。公式提出・Competition Rerun禁止。

## 事前判定条件

- 候補にする公開応答特徴は、各3 seed中2 seed以上に分布し、選択または応答の該当機会が全体10件以上あること。
- level 1完了との関連を示す場合、完了run内外の機会数を併記し、希少な8完了だけを根拠に因果と断定しない。seed間で方向が揃わない、または支持件数不足ならC2を作らずC1へ戻る。
- 関連が支持されてもC1監査だけで有効性を主張しない。C2へ進むなら、評価器だけのpaired ablation、事前安全gate、previous/current/deltaを別指示書で固定する。

## 完了証拠

- source/input/output SHA256、禁止key監査、seed別・全体の匿名aggregateを保存する。
- Kaggle公式score `0.25`への原因帰属をしない。公開25環境のRHAEは公式Kaggle scoreと別評価であることを明記する。
