# 非公開事前記憶を除いたbundleの実Agent同値smoke（2026-10-29）

## 対象と結果

非公開指定の事前記憶loaderを含まない実験bundleを一時領域に生成し、既存の私的bundleでloaderの投入を無効にした条件と、公開ゲーム1件・同じseed・80要求で比較した。両腕は代表点方針を使う。候補側では実Agentの方針・無記憶Adapterを評価器が上書きしないことをruntime guardと否定試験で確認した。

両腕で初期状態と行動列が一致し、SDK score 0／完了level 0、dispatchとstepは各80、最終frame無変化操作は各5だった。事前記憶読込0、HDS更新78・照会80、HDS Action認可false、SDK・Agent警告0、SDK操作数不一致0。非公開loaderのパス、同一ファイルbytes、静的importがcandidate bundleに存在しないことと、隔離subprocessでAgentのimport・生成を確認した。

代表点を使わない旧基準方針についても、同じ公開1ゲーム・seed・80要求で、私的bundleのloader投入無効とloaderを物理的に除いたbundleを比較した。初期状態・行動列が一致し、SDK score 0／完了level 0、dispatchとstep各80、最終frame無変化各5、事前記憶読込0、HDS更新78・照会80、認可false、警告・error・操作数不一致0だった。候補の実policyと実Adapterを上書きせず、代表点module不在と乱数選択1回をguardで確認。別の1ゲームではなく、同じ1ゲームである。

## 射程

これは**物理的にloaderを除いた構成と、私的bundle内で投入を無効にした構成の1ゲーム同値確認**である。代表点方針は公開25ゲームで平均SDK scoreが低下しており、得点改善版として採用していない。公開可能なHDSの範囲・Notebookの埋込物・実Kaggle Gateway・競技9時間・公式score・未見転移・学習効果は未確認。候補ZIPはHDSソースを含むため、公開許可や秘密の全面監査が成立するまで公開・提出しない。

次は代表点を使わない無記憶実Agentの構成について評価対象を広げ、観測に基づく改善候補と競技Notebookの要件へつなぐ。

## 根拠

- 匿名集計 `証拠/ARC3-v3-無事前記憶bundle同値smoke-20261029.json` SHA-256 `6c709f30be7aa5b3c51ec7b2142b81c5f1580ef74d008568862d89a512942d69`。
- 代表点なし基準版の匿名集計 `証拠/ARC3-v3-無事前記憶基準bundle同値smoke-20261029.json` SHA-256 `2147dc17eed14467595ddf7ff3015dee811fdec3ec93cbcc541d5a4d9d638b8b`、候補bundle SHA-256 `86eb6bdbc8d700001a94528813a8bb77f4a4c0029ed18f8416637560b46dd16c`、比較器 SHA-256 `9593db626fe626b619a4f60ac4e4031c36d5d88402d5ff5033f62a8a94eecc11`、guard SHA-256 `d1897742c909b368b55fdd5d4025005b86c37fd37ba934711fa888fa12764703`。候補bundleは公開しない。
- 候補bundle SHA-256 `a4688baff1d76d9a13ffd1fb5d33352003f02b2845fbb76330165ec30cbd4ba5`。比較器SHA-256 `b912faff386ee5377f111fd966a3483e96848b867d24900d22263f13a0f75bdd`、runtime guard SHA-256 `6751352a6a3580705f5ef585df126b75992a538b9872bd46c3c862134062265d`。候補bundleと私的対照bundleは公開しない。
- Windows、Python 3.12.10、arc-agi 0.9.8、arcengine 0.9.3。公開入力manifest 70ファイルのSHA-256 `a31a1da89a00032a91007599b71024a72caa812f784786e08605098393985367`、環境seed 0、方針seed 31025。比較時は別評価も稼働していたため、経過時間を公平比較しない。

この報告と匿名集計を新規作成した後に、編集前に必要だった二世代復旧refの更新漏れを発見した。既存変更とHEADを保護したまま、remote・local照合および競合検出付き更新で直近を `ba0f3732e45fad236a04dec35feeb1bbf29d0e18`、前世代を `bef4d20a3f2d69959ecbb45fd51349120c6cda24` に更新済み。次の編集ブロックからは着手前に更新する。
