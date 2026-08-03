# M4-P06 — Submission／Platform Separation

- Point ID: `M4-P06_SUBMISSION_PLATFORM_SEPARATION`
- Depends on: M4-P05 PASS + Owner explicit submission authorization
- Next: terminal

## 目的

同一release artifactを一度だけ提出し、transport、platform、competition score、sample製品完成を混同せず記録する。

## 必須作業

1. submission直前にartifact／Notebook identityを再確認する。
2. 明示承認された一経路で一度だけsubmitする。
3. terminal statusまで同一submission refを監視する。
4. status、public/private score、bytes、error、episode evidenceを記録する。
5. 結果を三分離する。

```text
transport_status
platform_execution_status
competition_score_status
```

6. M4-P04のsample product statusを別fieldで保持する。

## Hard Exit

```text
submission_ref_recorded = true
terminal_status_recorded = true
same_release_artifact = true
retry_without_authorization_count = 0
transport_platform_score_separated = true
```

## Claim Rules

- Notebook／submissionが`COMPLETE`でも、scoreが低ければcompetition completeではない。
- official scoreを得たこと自体は`PRODUCT_RELEASED`の根拠ではない。
- `ARC3_OFFICIAL_SAMPLE_PRODUCT_COMPLETE`はM4-P04 evidenceだけに依存する。
- `ARC3_COMPETITION_COMPLETE`は競技側の完全達成条件を満たす場合だけ。
- public score 0.06を成功、failureなし、product releasedへ変換してはならない。

## 出力Status

```text
SUBMISSION_RESULT_RECORDED
TRANSPORT_FAILURE
PLATFORM_FAILURE
COMPETITION_PARTIAL_SCORE
COMPETITION_COMPLETE
```

## 禁止

- low scoreをplatform successだけで製品成功扱い
- score未達をfailureなしと分類
- frozen artifactを監視中に変更
- 無断retry
