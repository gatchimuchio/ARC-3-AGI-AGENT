# Proposed Next Action

現在の許可済み状態は、rev3文書・契約の監査是正とCodex自己監査までである。

次の手順は次の順序に限定する。

1. OwnerがImplementation Commit `3be6aeb67ccb05b55c90bf876c8a16410b8c766e`、
   このEvidence Package、配布ZIPをreviewする。
2. Ownerが是正案の採否と`PH-R-1`開始可否を明示する。
3. Codexは明示判断を
   `OWNER_DECISION_CAPTURE_SCHEMA_V1.json`へ機械的に転記し、
   判断対象と判断本文のdigestを検証する。
4. Evidence Commitとは別のApproval Commitを作成する。
5. 承認された場合のみ`PH-R-1` Strategy Installationを開始する。
6. `PH-R-1`の受入条件とOwner承認が閉じるまで`PH-R00`を開始しない。

現在、strategyは`NOT_INSTALLED`、`PH-R00`は`SUSPEND`である。
Owner承認やphase開始をCodexが推定してはならない。
