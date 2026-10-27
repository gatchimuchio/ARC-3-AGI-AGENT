# ARC3-RUN-003 C1-021：公開25環境のmodel v5 token深度監査

## 対象・条件

正本v3.0のC1-021指示書に基づき、保存済みpublic v5 benchmark、25件のevent stream、summaryをread-onlyで集計した。event stream中の公開`level`をaction前深度として使い、benchmarkとのrun対応は処理中だけ行った。出力は深度別と終了上限群別の匿名aggregateのみ。Notebook、model、prompt、runtime、policy、HDS、agent変更およびKaggle操作はない。

## 結果

- 25/25 runがevent historyと整列し、Action数1,906。history generated-token合計2,134,037はsummaryのtotal tokensと一致した。
- 深度別のgenerated-token使用量：

| 公開深度 | Action数 | generated tokens | token記録ありAction | 平均tokens/Action |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 815 | 829,604 | 271 | 1,017.92 |
| 2 | 664 | 828,680 | 175 | 1,248.01 |
| 3 | 275 | 275,588 | 65 | 1,002.14 |
| 4 | 92 | 133,382 | 30 | 1,449.80 |
| 5 | 54 | 55,898 | 10 | 1,035.15 |
| 6 | 6 | 10,885 | 3 | 1,814.17 |

深度に対する平均token量は単調増加しない。深度5・6は標本が54・6 Actionと小さく、深度依存を示す根拠にはならない。

| 終了上限群 | run数 | Action数 | generated tokens | 平均tokens/Action |
| --- | ---: | ---: | ---: | ---: |
| 80 Action到達 | 21 | 1,680 | 1,585,051 | 943.48 |
| 80未満（C1-019で1200秒capと照合済み） | 4 | 226 | 548,986 | 2,429.14 |

1200秒cap群の平均は80 Action群の約2.57倍（差+1,485.66 tokens/Action）。4 runのみの選択群であり、より多い生成tokenがruntime capを引き起こしたとは断定できない。行動選択・勝利・scoreへの因果効果も示さない。

`uncached_input_tokens`は1,906 Actionすべて0で、入力token増加は計測値から評価不能。history内`wallclock_seconds`の最大値15,654.225秒はbenchmark経過時間15,657.695秒に3.470秒まで近い。Action単位の推論遅延を表すと確定できないため深度別遅延としては採用しない。

別計測の`solver_note` token合計は2,162,266でhistory合計より28,229多い。両カウンタの範囲を特定できる出所は保存資料から確認できていないため、summaryとの一致判定には使わず未解決差分として記録する。

## 採否・限界

**入力token増加または深度別遅延を根拠とするmodel変更は不支持。** 出力tokenの深度傾向も単調でなく、cap群との差は少数runの相関に留まる。別カウンタ間の28,229差は再照合事項だが、この差だけで推論負荷や性能を結論しない。今回は匿名の読取専用監査器と集計JSONのみを追加した。

限界：固定model/prompt、保存済み公開25環境、単一benchmarkの記述統計。Input token欄の意味・wallclock欄の単位範囲・`solver_note` token計数の出所が未確定で、runtime capの原因や公式scoreの変化を説明しない。

## 検証・出所

- Targeted tests：`2 passed`。Ruff check／format、`py_compile`もPASS。
- 匿名aggregate：[`C1-021 JSON`](../../出力/ARC3-RUN-003-local/C1-021-model-v5-token-depth.json)。出力schemaに個別run、識別子、board、Action列はない。
- 解析器：[ARC3ベンチマークtoken深度監査.py](../ARC3ベンチマークtoken深度監査.py)、tests：[test_ARC3ベンチマークtoken深度監査.py](../test_ARC3ベンチマークtoken深度監査.py)。
- source：benchmark `7237a2d2150820ee2aadc8ba986dcb67a12e495bd934bd686583b1cd32ebdcd2`、summary `38d0954973a4cbb1d7c94b94463b100fdb18d3f760849b411e248f072a0f21ac`、C2-027 comparison `4bd0bf8b3f966f098d0a8ddca98038f1abdd8a5836af02718d528fb2282a730b`。25 event content-set SHA256 `d8653cb231ed8e07d16c9b1f4ee82a20c664da98d896da3e266ec78f9e0fdeac`は、filename順に並べた各event fileのSHA256をLF区切りで連結した文字列のSHA256（filename自体は含めない）。
- 指示書SHA256は`ARC3-RUN-003-C1-021` ledger entryに記録。解析器SHA256=`b87c16b50b213254c42b53a6153a45d547198f22700adacd8d0ddc4fe952fea2`、tests SHA256=`0de8833bc513caf20aa623767129c215e6ec30a629cda21b08909052946d8872`。
- 集計JSON SHA256 `1e5cd3427a5f84101da528e37632ca45b9227adace7e978f50204ededdc24bb7`。

## 再開点

C1-021は局所的に完了。C1-018の公式提出`57577905`は最後のread-only照会（02:16 UTC）でPENDING。本日残り提出枠0のため再提出せず、30〜60分間隔の同一ID照会を継続する。次の作業候補は`solver_note`とhistory generated-tokenの28,229差について計数範囲を出所コードから特定すること。変更案・性能最適化は作らない。
