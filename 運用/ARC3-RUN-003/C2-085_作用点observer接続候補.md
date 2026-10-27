# C2-085 作用点observer接続候補

## 目的と状態

C2-084の同一記録上の予測改善を、C2-081のモデル候補照会へ接続するLOCAL候補を準備する。1ゲーム内のoffline +7正解は実行方策・得点・汎化の証拠ではなく、正本昇格しない。実行待ちのC2-081 shown-r2は元の二値応答版として保持し、sourceを混ぜない。

## observerの変更範囲

追加はAction6に限る次の2点。

1. 操作前targetを含む同色4連結領域の正確なpixel数を、query/update共通の操作前特徴へ追加する。
2. 実応答から操作前target中心7×7内と外の変化有無を測り、4categoryの`公開作用点効果区分`を教師へ追加する。

非Action6では新項目を省略し、0や偽の座標を発明しない。元の公開応答・レベル進行・失敗署名とRESET/automatic除外を保持する。遠隔だけの変化を無反応・失敗・HUDと断定しない。before/afterが不足・不整合なら新effectはunknown/省略し、元の失敗/進行まで消さない。

連結成分の形状・方向・物体同一性・閾値bin・ID分岐は追加しない。元のnative0.4.2は変更せず、C2-079 scope patchやC2-084のoffline fallbackを実行方策へ入れない。

## 実行候補と採否

凍結C2-081 r2のhelper/RPC/session/計測を再利用し、同じ新observer・prompt・native・bundle・model/予算でmasked/shownを構築する。実nativeのHOLD/未確定予測を保ち、元の応答と新局所応答の両方を不確実性付きで返す。Action認可・推奨は生成しない。SDK合法性・厳密な座標・実行後一回更新・cache/予算・独立視覚探索のfallbackは維持する。

数学helper/入力差分/PRE非漏洩/欠落/RESET/純粋照会のCPU検査と独立sourceレビュー後、別の同source private比較で得点を測る。C2-081との直接deltaを対応比較としない。同版反復・公開全25・情報提示と学習更新の効果の区別・公式最高23.86更新の要件を保持する。

並行するC2-086は新seed3701の公開25ゲームで1項目を検証するnative予測診断で、実ゲーム方策や公式score評価の代わりではない。全公開集合は既に再利用しており、未使用ベンチマークとは呼ばない。候補はCPU検査・独立監査を完了し、Kaggle未送信。

## CPU候補の成立範囲

2026-10-27T01:18:47Zのproofは `出力/ARC3-RUN-003-local/C2-085/arms-preflight.json`、SHA-256 `4ebce39be17f0e9207d7c17155c6f8d016845547d4acee30361cf3dbddd45656`。14 focused tests・Ruff・32固定数学oracle・実nativeへ渡すquery/teacherのPRE一致を確認した。native12ファイル・prior・bridge・元runtime・solver・Python RPCは凍結元と同一で、ToolAgentの変更は共通promptの幾何説明だけ。既存C2-081の両artifactとsourceも不変。

共通bundleは `d66a348026852a9a8e3286d22ae7dfacb10b7cf7d7b26ae8c8cbf33862418312`。masked Notebookは `3c5f1b74ca489fd565df8f8fe557de51b36502625ff2b297c79233971c0a1c4b`、shownは `14ad90b5dd4c5ee4fa373420431f01ec0526b2613788efb1a8276b738b5c1bc9`。両者の差はvisibilityとid/titleだけ。独立source/数学/arm監査に阻害事項なし。

CPUでの接続成立であり、Linux/GPU・モデルによる情報利用・攻略得点の改善は未確認。C2-086の広い診断は12完走/13予算途中で、予測の小差も途中終了した2環境へ集中した。これを昇格根拠にしない。次の主たる学習検証は、同じobserverを使うC2-087の両shown・prior-only対onlineで準備し、本visibility比較を完了扱いしない。
