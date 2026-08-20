# Repository Authority Model

この文書は、repositoryの**規範権威と観測事実の関係**を定義する。
現在Point、score、product status等の可変状態は保持しない。

## 1. Normative Authority Plane

規範上の優先順位は次の通り。

1. Ownerの現在の明示指示
2. root `AGENTS.md`および対象pathに適用される下位`AGENTS.md`
3. `docs/architecture/AGI三主体統合設計正本_v0_2.md`
4. `docs/references/HDS_FRAMEWORK_rev3_1a_INTERNAL.md`
5. `control/CURRENT_SELECTOR.json`の`spec_path`が指す現行仕様
6. 同Selectorの`roadmap_path`が指す現行ロードマップ
7. 同Selectorの`current_task_path`が指すCurrent Task
8. 同Selectorの`active_instruction_path`が指す局所指示

下位文書は上位文書を具体化できるが、上位の目的・責任境界・禁止事項を暗黙に変更できない。
戦略を切り替える場合はSelectorを更新し、root運用契約へ戦略内容をコピーしない。

## 2. Execution Selection Plane

「今どの戦略・Task・Instructionを実行するか」の唯一の入口は、

`control/CURRENT_SELECTOR.json`

である。

Current Task、Roadmap Manifest等に同じstate値が存在する場合、それらはSelectorに選択された**整合確認対象**であり、独立したcurrent selectorではない。
不一致は自動的に新しい正解を選ぶ理由ではなく、修復すべき状態不整合である。

## 3. Observed Reality Plane

次は権威文書ではなく、現実に何が成立しているかを示す観測面である。

- current source code
- testsおよび実行結果
- runtime trace／report
- local／offline評価結果
- official sample result
- Kaggle／platform result
- accepted score

規範文書に「完成」と書かれていても、観測面が未成立なら能力は未成立である。
逆に、観測されたfailureを古い完成claimで無効化してはならない。

```text
Authority decides what should be done.
Evidence decides what has been established.
```

## 4. Conflict Rule

規範と観測が衝突した場合は、次のように扱う。

```text
Target says PASS + Evidence says FAIL
=> FAIL is the observed state; target remains the repair objective.
```

```text
Target says forbidden + Existing code does it
=> code existence does not authorize the behavior; it is an implementation gap.
```

```text
Historical claim says COMPLETE + Current selector invalidates it
=> historical evidence is preserved, current authorityは持たない。
```

矛盾を無言で統合・平均化・再解釈しない。

## 5. Historical Plane

以下は原則としてhistorical evidenceである。

- `docs/history/`
- Selectorから選択されない旧strategy／roadmap／instruction
- Selectorから選択されない旧control state
- 旧release／submission／approval record
- 旧completion claim

historical assetは再利用可能な実装・知見・失敗証拠になり得るが、現在の作業を選択したりcompletionを宣言したりできない。

## 6. State Drift Prevention

次のstable surfaceへactive strategy ID、active Point ID、current score等を転記しない。

- `AGENTS.md`
- `AUTHORITY_ORDER.md`
- root `README.md`
- `docs/README.md`
- `docs/operations/`
- implementation subtreeのREADME／AGENTS

Current Stateを確認するときはSelectorを読む。
`python scripts/check_repository_environment.py`は、この分離とSelector整合を機械監査する。
