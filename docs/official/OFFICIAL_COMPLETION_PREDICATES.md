# ARC3 Official Completion Predicates

- predicate set ID: `ARC3_OFFICIAL_COMPLETION_PREDICATES_REV2`
- phase introduced: `P16`
- status: `PASS`

## Required score record

```text
submission_ref
submission_status
output_bytes
score_returned
raw_score
normalized_score_ppm
scope = PUBLIC_55 | PRIVATE_55 | FULL_110 | UNKNOWN
runtime_identity
runtime_package_logical_digest
runtime_package_byte_digest
p_logical_digest
notebook_version
notebook_source_digest
```

## Accepted run

```text
OFFICIAL_RUN_ACCEPTED
=
submission_status == COMPLETE
AND output_bytes > 0
AND score_returned
AND exact_runtime_package_digest_verified
AND exact_p_logical_digest_verified
```

Notebookの通常実行`COMPLETE`、ローカルparquet、提出API受理だけでは成立しない。

## Public

```text
OFFICIAL_PUBLIC_COMPLETE
=
OFFICIAL_RUN_ACCEPTED
AND scope == PUBLIC_55
AND normalized_score_ppm == 1_000_000
```

## Private

```text
OFFICIAL_PRIVATE_COMPLETE
=
OFFICIAL_RUN_ACCEPTED
AND scope == PRIVATE_55
AND normalized_score_ppm == 1_000_000
AND exact same RuntimeIdentity and artifact as the bound Public result
```

## Full

```text
OFFICIAL_FULL_COMPLETE
=
(
  same exact artifact PUBLIC_55 == 1_000_000
  AND same exact artifact PRIVATE_55 == 1_000_000
)
OR
(
  organizer-exposed FULL_110 == 1_000_000
)
```

## Negative classifications

```text
ERROR or score_returned == false or output_bytes == 0
→ OFFICIAL_NOT_OBSERVED
```

```text
OFFICIAL_RUN_ACCEPTED and normalized_score_ppm < 1_000_000
→ capability shortfall
→ trace witnessなしなら AUDIT_INCONCLUSIVE_CAPABILITY_SHORTFALL
```

```text
PUBLIC_55 == 1_000_000 and PRIVATE_55未観測
→ OFFICIAL_PUBLIC_COMPLETE
→ OFFICIAL_FULL_COMPLETEではない
```

## Current baseline classification

baseline commit `baa03f3`に保持される提出証拠はscoreなし・output bytes 0の
system errorであり、`OFFICIAL_NOT_OBSERVED`である。Notebook version 10の
通常実行証拠は`PREFLIGHT_ONLY`である。

公式結果を開発へ利用した場合、その結果は次RuntimeIdentityのdevelopment signalに
降格する。同じartifactの完成claimを後付けで変更しない。
