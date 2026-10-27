# ARC3-RUN-003 C2-072〜073 level-progress credit

## 結論

公開探索traceの集約では、現行visible-change係数0.0、seed0の25 gamesでAction6に464回（99 no-op）、level event 3件が集まり、他Actionのlevel eventは0だった。これは記述的な相関で、Action6の因果的優越を単独で証明するものではない。

その診断からlevel-progress credit 4→16をdevで比較し、15対ではRHAE差`+0.101437`・level差`+1`とgateを通過した。しかし、別seed 101/211/307の25公開game×3 seed holdout 75対では差0、75同点、level差0。**devで見えたgainは新しいseed群へ再現せず、係数16は棄却。runtime/HDS/提出agentは変更しない。**

公式competition submission、Competition Rerun、Notebook/kernel操作、quota利用はない。公式public scoreは本作業では再確認していない。

## 行動応答の記述集計

25公開game、各policy最大80 actions、seed/policy-seed0、`visible_change_coefficient=0.0`。exploration local policyはrandom policyよりRHAE平均`0.190476→0.306975`（差`+0.116499`）、level合計`1→3`、no-op`396→141`、WINは両方0。この比較は探索policyとrandomのlocal diagnosticで、HDS提出agentの公式score比較ではない。

探索policyのAction6は464/1689 actions、no-op99、level event 3、GAME_OVER5、mean public response reward0.205819。Action1-5/7はlevel event各0。リポジトリ内のaggregate JSONにはgame ID/ゲーム別traceは含まない。計算用raw traceは一時的に`%TEMP%\arc3-v6-action-attribution-20261027.json`と`%TEMP%\arc3-v6-action-attribution-current-20261027.json`にあり、cleanup要求はtool policyに拒否されたため残存している。2ファイルとも公開local evaluation出力だが、game ID/Action traceを含む。

## C2-072 dev: credit 4→16

固定条件: current visible-change coefficient0.0、split seed20261027のdev5 game、environment/policy seed7/31/73、80 actions上限、hash seed0。15対でbaseline RHAE`0.0926863272`、candidate`0.1941233517`、差`+0.1014370245`。改善/後退/同点`1/0/14`、level差`+1`、WIN差0、no-op差`+3`、Action6差`+12`、GAME_OVER差`−1`、trace変更2、初期状態一致15/15、illegal/error/duplicate0。改善はseed7の1対のみで、seed31/73はscore同点。事前dev gateを通過しC2-073へ進んだ。

最初の出力はvisible-change係数0.25で実行され、現行policy条件に合わないためsuperseded。r2を使う。

## C2-073 seed holdout: 4→16

全25公開game、devと異なるenvironment/policy seed101/211/307、75 paired runs、hash seed0。baseline/candidate RHAE平均は両方`0.2594179528`、差0、改善/後退/同点`0/0/75`、level/WIN差0、初期状態一致75/75、illegal/error/duplicate0。action trace変更9、Action6差+24、actions差+25、no-op差+2、GAME_OVER差−1は得点差につながらなかった。事前seed-holdout gate不合格。未見game ID holdoutの結果とは呼ばない。

## 機械可読証拠・source

| Artifact | SHA-256 |
| --- | --- |
| current-policy Action/response aggregate `P1-3_public-action-response-attribution-current_20261027.json` | `323f551bc522e804fff27b196424b184fa172c44cdc2fea4367b35d8f7a7e394` |
| superseded 0.25 condition `P1-3_level-progress-reward16-dev_20261027.json` | `655575aaca0604fb50da28c68ced3982792bce08ca08fb950a3c7c5bc5b99744` |
| C2-072 current-condition dev `P1-3_level-progress-reward16-dev_20261027_r2.json` | `5bdbef56ee6265411b69b8b890a43f9c848d84954cdbe223290c43f9a9e01075` |
| C2-073 seed holdout `P1-3_level-progress-reward16-seed-holdout_20261027.json` | `9d775b9ba77aa0de3dd1390ef76bad685045aef659809dd33a4bc322cb564270` |

Current policy SHA `7879f85b5a3434dc2f5426c4837914c41054cbe56360ed4324167dab93de0575`; public input manifest SHA `924f0da0af3bd3b8ac4fa742f35a48f0bf367567f55e8a299588ea710202d97a`. Aggregators store no game IDs or per-game rows. Candidate coefficient 16 remains evaluation-only.

## 検証状態

固定uv環境でRuff check/format、`py_compile`成功。関連pytest `33 passed, 3 subtests passed`。`git diff --check`に空白エラーなし（既存CRLF警告3件）。`AGENTS.md`、`制御/現在状態.json`、tracked Notebook差分なし、staged変更なし。

## 次の判断

credit倍率を上げる方向は停止する。Action6について、選択時の公開盤面特徴と公開応答をもう少し因果に近づけて匿名集計し、進行イベントを予測する再現可能な情報があるかを調べる。候補がdevで通った場合も、次回は未見seedでの再現に加え、現HDS提出agentを使った同一条件full local scorecardで別途確認する。
