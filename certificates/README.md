# Executable certificates

このdirectoryはphase gateを通過した決定論的証明artifactだけを保持する。

## P9

`p9/`は`arc3-build-minimum-certificate`で生成するAGI最小三構成certificate
5件を保持する。手編集しない。正本の生成入力は
`docs/architecture/AGI_OBLIGATION_GRAPH.json`、実行実装は
`ARC-AGI-3-Agents/arc3_agi_agent/certificate.py`、検証は
`ARC-AGI-3-Agents/tests/unit/test_minimum_three_certificate_p9.py`である。

P9の証拠境界とdigestは
`docs/architecture/P9_MINIMUM_THREE_CERTIFICATE.md`を参照する。
