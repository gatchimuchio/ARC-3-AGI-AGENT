# release/ — Historical Release Artifacts

このdirectoryにあるrelease資産は**CURRENT releaseではない**。

rev6ではrev5.1の`M2_COMPLETE`、`M3_COMPLETE`、`RELEASE_FROZEN`、`ARC3_COMPLETION_AGENT_PRODUCT_RELEASED`を製品完成証拠として失効している。

保存対象:

- `ARC3CompletionAgent-v1.0/`
- `rev5_1/`

これらは削除せず、過去のpackage構成・依存・提出経路・失敗解析の証拠として保持する。

Current product status:

```text
NOT_ESTABLISHED
```

新しいreleaseはrev6 roadmapのM4を通過し、同一artifactによるclean rerunとKaggle normal runを満たした場合のみ作成対象となる。旧releaseをrelease parentまたはcompletion evidenceとして使用しない。
