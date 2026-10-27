# ARC3-RUN-002 C4-003 色統計resetによるGAME_OVER転移確認

- 実施日: 2026-10-23 JST
- 指示: `運用/ARC3-RUN-002/C4-003_色統計resetのGAME_OVER転移確認.md`
- 判定: **GAME_OVERは2件減ったがno-opが29件増加し、候補を棄却。**
- 対象: 固定holdout 20公開環境×seed 7/31/73、最大80要求、GAME_OVER後SDK RESET。

## 結果

| seed | 完了level previous→candidate | no-op previous→candidate | GAME_OVER previous→candidate |
| --- | ---: | ---: | ---: |
| 7 | 1→1 | 150→160 | 10→9 |
| 31 | 2→2 | 128→138 | 9→8 |
| 73 | 2→2 | 137→146 | 10→10 |
| 合計 | 5→5 | 415→444 | 29→27 |

previous 60 runはC2-003保存済みholdout各seedの全基準集計と一致し、全60対で開始状態・level数・合法Action・盤面も一致した。候補は完了levelを維持し、GAME_OVERをseed7/31で各1件減らした一方、no-opを全seedで10/10/9件増やした。HOLD・illegal・duplicateは0。no-op非劣化条件に不合格のため、GAME_OVER減少だけでは採用しない。

## 判断

C4-002 devではGAME_OVERが18→16、no-opが35のままだった。holdoutではGAME_OVER減少は一部で再現したが、no-op悪化が明確に増幅した。色統計resetをcandidate version 4へ採用せず、HDS・runtime policy・Notebook/kernelも変更しない。結果はローカル公開環境に限り、公式score改善を示さない。

## 検証と証拠

- 匿名aggregate: `出力/ARC3-RUN-002-local/C4-003-level-color-gameover-holdout.json`、5,872 bytes、SHA-256 `769cdd857f7f240eb968bb8b5972b411f5fbeae381226844c540fcf04b9aa5e0`。識別子・座標・盤面を含まない。
- 実験runner `検証/ARC3レベル間色統計GAME_OVER確認.py`: SHA-256 `47e7d1b5ae4244e0f6677c20266a7d7a6988aa9a6b0c28290b70f4bcc22d69f1`。
- holdout runner `検証/ARC3レベル間色統計評価.py`: SHA-256 `6ef2034065e7ef81b0c08570fe05bba072317d029338410ce0522be2a3cf1ef2`。
- 共通評価runner `検証/ARC3探索Actionローカル評価.py`: SHA-256 `e7d87ff3df4ef1e1aab1d226fdb6fdc0a9a46bede5c450c71f31ae57c1239fb0`。
- test `検証/test_ARC3レベル間色統計GAME_OVER確認.py`: SHA-256 `7a5e55cfa0739a58cd658b5c17a1deaddc906bab217ec344d5c2b646b0016967`。関連test 7 passed、対象Ruff・compileall pass。
- policy SHA-256 `325666ae54197474e33b4ff46306abc7ad12c7a489d2c2c3c59585d887e26510`は維持。
