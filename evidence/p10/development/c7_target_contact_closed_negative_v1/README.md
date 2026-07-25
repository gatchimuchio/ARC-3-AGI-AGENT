# C7 target-contact closed-negative admission

このdirectoryは、P3 provenance manifestで凍結済みのC7 harnessを現行P10へ
負の証拠としてだけ移植したもの。retained sourceのSHA-256
`cf52951e7bc4c85aa29a2bff217f298b558fc5d3dad6312c3bde1c8575883032`
と2,232,464 bytesはmanifest記録と一致する。

保持値:

- target contract: 7
- probe: 288
- visible change: 228
- target-contact gain: 63
- level progress: 0
- GAME_OVER: 0
- progress separator: 0
- hazard separator: 0
- reusable hazard separator: 0
- promotion-eligible variable: 0
- error: 0

legacy artifactの`probe_artifact_matches_contract_spec=false`は隠さずquarantine
する。このため証拠はsame-surface retryを閉じる用途に限って採用し、positive
generalization、Runtime P compile、promotion、score claimには使用しない。
HDS判断は`REJECT / CLOSED_NEGATIVE`で、次の未埋込high-support work blockは
`WB-C12_layout_mode_commit_discriminator`である。

| artifact | SHA-256 |
|---|---|
| retained legacy source | `cf52951e7bc4c85aa29a2bff217f298b558fc5d3dad6312c3bde1c8575883032` |
| negative-only admission audit | `8da9bb9c7f99dc3bdfdc6cb8962f7428142a2bac39b1470a509a75891b17b9e0` |

admission content digest:
`arc3_p10_c7_closed_negative_admission:fa5b1d4fcdf7a8584093a8ee81547a9fe29a76159b39e45e693c6e90ac2b9729`
