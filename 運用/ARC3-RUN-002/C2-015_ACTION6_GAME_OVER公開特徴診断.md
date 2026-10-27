# C2-015 指示書：ACTION6 GAME_OVER直前の公開特徴診断

- 指示ID: `ARC3-RUN-002-C2-015`
- 版: 1.0／2026-10-23（JST）
- 根拠: C2-014 devのprevious 18 GAME_OVER中15件はACTION6後だった（各seed5件）。-1.0終端罰はGAME_OVER 18→19となり不採用。終端直前の観測特徴を調べずに罰係数を追加調整しない。
- 目的: ACTION6後にGAME_OVERとなる応答と、通常変化・level進行・no-opの直前公開特徴に再現可能な差があるかを読み取り専用で診断する。

## 方法

- 固定dev 5公開環境×seed 7/31/73で候補v4相当方針を再実行し、ACTION6応答だけを観測する。
- action前の公開盤面から、C2-011と同じ選択色頻度・同色4近傍・相対中心距離bucketを数える。応答後はGAME_OVER、level進行/後退、no-op、board changeの順で排他的に分類。
- policy、報酬、HDS、runtime、Action選択は変更しない。識別子、座標、盤面、軌跡は出力しない。
- 既定dev baselineのactions・levels・no-op・GAME_OVER・RESET・HOLD・illegal・duplicateに一致しなければ診断を無効とする。

## 判定境界

- 同じdev集合の小標本bucket比率は因果・安全規則の証明ではない。複数seedで反復する候補特徴を報告しても、新しい規則の採用やholdout使用は行わない。
- 十分な反復がなければ「有用な事前特徴なし」と判定し、係数を追加しない。次はC2-010 Action別GAME_OVER集計または公式Rerun結果から別の原因層を選ぶ。

## 成果物

- 匿名seed×condition×feature bucket×outcome aggregate、baseline一致、tests、source/output SHA-256、解釈境界を `検証/運転記録/ARC3-RUN-002_C2-015_ACTION6_GAME_OVER特徴診断_20261023.md` に記録する。
