# C1-003 指示書：公開応答の複数frame情報利用監査

- 指示ID: `ARC3-RUN-002-C1-003`
- 版: 1.0／2026-10-23（JST）
- 対象: ARC3 `FrameData.frame` と観測駆動Actionの入力
- 前工程: C5-001上限拡大を棄却し候補version 4を維持

## 根拠と仮説

公式starterは`FrameData.frame`を複数gridの配列として変換する。`接続/ARC3境界.py`は全gridを`観測.盤面列`に保持するが、探索方針は`観測.最新盤面`だけを使い、HDS候補照会も最新盤面だけを構造語彙へ渡す。公開応答に最終grid以外の異なるgridが存在すれば、現行のAction選択経路はその情報を使っていない。これらのgridの意味がアニメーションか他の状態かは、観測結果だけで断定しない。

## 目的・範囲

固定した候補v4方針・seed 31・1ゲーム80 Action以内で25公開環境を診断し、応答frame数、異なるgrid数、最終gridに残らない途中差分の頻度と大きさを集計する。Action選択へ中間gridを接続する実装・係数変更・HDS更新・Notebook更新は行わない。

## 保持条件

- 25公開環境すべてを一度ずつ評価し、ID/name/hashをAction選択や分類条件に使用しない。
- Action/RESET/WIN/level増分の意味はSDK上の一回の環境応答単位で保ち、途中gridを独立Actionや成功と扱わない。
- 全gridの順序を保持し、盤面寸法不一致や欠損は例外へ隠さず診断結果へ記録する。
- ローカル出力は匿名集計とし、正解・hidden state・問題専用規則を導入しない。
- `AGENTS.md`、`制御/現在状態.json`、正本pointer、v2.0文書、HDS v0.4.2、候補v4 bundleを変更しない。

## 手順と判定

1. starter/arcengineの現行FrameData契約と、境界・HDS照会・探索方針の実装を再読する。
2. 25公開環境を同じsplit seed `20261022`、Action seed31、上限80、GAME_OVER後RESET有効で実行し、応答内のgrid列を集計する。
3. `len(frame)>1`、相異なるgrid数、前grid・各途中grid・最終grid間のセル差分、途中で変化して最終gridに残らないセル数を集計する。途中gridの意味や有用性は推測しない。
4. 入力契約・合法Action・最大要求数・HOLD・illegal/duplicateの既存条件に変化がないことを確認する。
5. 複数grid/差分が再現可能に観測された場合、次に中間情報利用の一要因実験を別指示書で設計する。十分な頻度がなければ中間gridをruntimeへ接続しない。

## 成果物

診断runner、targeted tests、匿名集計JSONとhash、25環境での計測範囲・欠測・previous/currentの情報可視範囲、採否、次工程を `検証/運転記録/ARC3-RUN-002_C1-003_複数Frame監査_20261023.md` に記録する。候補v4の提出SHAは変えない。
