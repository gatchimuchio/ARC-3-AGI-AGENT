# M4-P05 — Kaggle Package／Normal Run

- Point ID: `M4-P05_KAGGLE_NORMAL_RUN`
- Depends on: M4-P04 PASS
- Next: `M4-P06_SUBMISSION_PLATFORM_SEPARATION`
- Capability change: 禁止

## 目的

M4-P04でPASSした同一release artifactをKaggle Notebook／entrypointへ配置し、通常実行経路を確認する。

## 必須作業

1. frozen artifact identityを再確認する。
2. Notebookへ同一wheel／packageを配置する。
3. dependency installをoffline契約で確認する。
4. official I/O、scorecard lifecycle、output contractを確認する。
5. normal runを完了する。
6. output fileの存在、型、列、bytesを記録する。

## Hard Exit

```text
same_release_artifact_as_M4_P04 = true
capability_change_count = 0
normal_notebook_run = COMPLETE
entrypoint_count = 1
output_contract = PASS
secret_finding_count = 0
submission_API_call_count = 0
```

## 禁止

- Notebook向けpolicy変更
- fallback／replay追加
- normal run完了をcompetition成功扱い
- このPointでsubmission

## Failure Routing

transport／package問題は本PointまたはM4-P02へ戻す。能力問題はM4-P04以前へ戻す。
