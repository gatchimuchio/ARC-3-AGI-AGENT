# C1-004 指示書：複数frame応答とno-op判定の重複監査

- 指示ID: `ARC3-RUN-002-C1-004`
- 版: 1.0／2026-10-23（JST）
- 対象: C1-003で観測した複数grid応答とC2-003 no-op罰
- 基準: 候補v4、80 Action、探索報酬no-op `-1.0`

## 根拠と仮説

C1-003で25公開環境の2,000応答中654件（32.7%）が複数gridだった。現行方針の変化数は作用前・応答最終gridのみを比べ、最終grid不変かつlevel増分なしにはno-op罰を与える。複数grid中間差分を含む応答が現行no-opと重なる頻度を調べれば、no-op判定が途中の公開変化をどう扱っているか、別の一要因実験を検討する証拠になる。

## 範囲と保持条件

- 候補v4方針・係数・Action要求上限を変更しない。HDS/Notebook/kernelも更新しない。
- 全25公開環境、action seed 7/31/73、各80要求を固定実行し、Action・中間grid・最終grid・level増分を応答単位で対応させる。
- 現行方針のno-op判定を「非RESET、最終盤面同一、完了level増分0」として再現し、複数gridや中間差分との一致を匿名集計する。
- game/level ID、filename、hash、trajectory、答えをAction選択・分類規則に使わない。出力はAction種別×seedの集計で、ゲーム識別子を含めない。
- 相関を因果・改善・公式scoreと呼ばない。途中gridを独立Action、成功、追加stepとして扱わない。

## 手順と判定

1. C1-003の診断コード、候補no-op定義、C2-003固定出力を変更前証拠として固定する。
2. 25環境×3 seedの応答を同じ探索policyで再生し、応答単位でno-op、複数frame、中間gridが最終と異なる、最終盤面変化、level進行を記録する。
3. 3 seedそれぞれで既存C2-003の全run action/no-op/level集計に一致することを照合し、計測追加がpolicy順序を変えないことを確認する。
4. no-op内の中間差分の割合とAction群別偏りを出す。希少、単一Actionに偏る、seedで再現しない場合はruntime利用候補を立てない。
5. 複数Action・複数seedで再現し、既存holdout上でlevel進行との関係を観測しても、なお次の一要因runtime実験は開発splitで別途評価する。C1-004自体は変更を採用しない。

## 成果物

新規のread-only監査runnerとtargeted test、匿名aggregate JSON+SHA、3 seedのprevious/current照合、no-op/複数frame/中間差分/進行数、採否と次課題を `検証/運転記録/ARC3-RUN-002_C1-004_Frameとno-op重複監査_20261023.md` に保存する。既存artifactは上書きしない。
