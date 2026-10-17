# 保存期限・計算期限の失敗原証拠

## 目的・観測・原因・変更

保存と計算の資源境界で停止した二つのrunを、失敗したまま一次教材として保持する。元の作業directoryは再起動後に未回収だったが、Libraryの原配布archiveは既知SHA256と一致して復旧した。今回、原archive、完全manifest、独立内容検査と索引を非runtime運転記録へ追加する。

## previous / current / delta

- previous: `9a654e1ae54f7f162240a22de7978edf1e062338`。原archive保存は5/14本。
- current: 保存期限失敗と計算期限失敗の原archiveを追加。過去の報告・raw・状態・source・未完了入力・失敗保存を保持する。
- delta: 障害の再現条件と境界がGitで追跡できる。修正、再実行、能力向上の主張ではない。

## 成立した観測と停止原因

1. 保存期限失敗 `fbc3a451…`: Query ordinal642のreply保存で累積save120秒の期限へ到達。二次的な重複failure packetは16MiB typed上限を超えた。29 Actions、643 Queries、Teach0を記録。step29は未完了で、許可されたCtrl-Cによりexit130で閉じた。
2. 計算期限失敗 `13666f59…`: step58・Query ordinal1331付近で累積compute900秒の期限へ到達。58 Actions、1,332 Queries、Teach0を保存し、exit1で閉じた。

ここでの回数は歴史的runの記録であり、今回の実行回数ではない。途中の公開level値2や4を新たな認証済み達成へ加算しない。認証済み成功は引き続き1/183（約0.55%）。全game WINを示さない。

## regression

保存期限archiveの2,807member、JSON2,737件、XZ1,876本と、計算期限archiveの4,114member、JSON4,092件、XZ2,959本を全数検査した。外側gzip CRC/EOF、元manifestの全サイズ・SHA256が一致した。保存失敗の `.bytes` 3件は自作producerの型付きJSON replyをXZで保持したものとして由来を確定して検査した。公式SDKのopaque streamではない。

自作sourceは静的検査のみ。失敗source・pure fixture・途中packet・失敗説明を削除しない。既存mainのblobと保護対象を変更しない。

## limitations

二つともFAILEDの証拠であり、mainの採用runtimeに混ぜない。現在の接続での再現、fresh043、速度改善、汎化や新規クリアを認証しない。native HDS / Query / Teach / SDK / Actionは出版作業で実行しない。

外部依存のFileRefは本体の保存を意味しない。公式game/SDK実装やopaque出力本体は収録せず、由来が確定した自作metadataと公開観測だけを検査した。大容量archiveはremote Git blob SHAとtreeサイズで内容identityを照合する。大容量全bytesの独立remote stream読戻しはconnectorの制限で未実施。metadataは全内容を読み戻す。

原archiveのSHA256と完全manifestの対応は `失敗原証拠索引.json` に記録する。別のgoal曖昧性失敗と他の歴史資料も引き続き保存対象であり、全成果保存済みとはしない。

## 計算期限archiveのbyte分割保存

接続toolの1request 16MiB上限により、計算期限archiveだけは `.part01` と `.part02` の連続byte範囲で保存した。各partは独立したtarではない。順番に結合すると元の13,696,451 bytes、SHA256 `98bb631629373e59ba642ba65077a1dd3952a038d42331e43a2c483b383d902a` に完全復元できる。元archive自体は変更していない。索引のoffset・bytes・SHA256を各partについて確認し、既存ファイルを上書きせず結合する。

例（この保存directoryで、Python標準ライブラリのみ。archive内sourceは実行しない）:

```python
import hashlib, json
from pathlib import Path
m = json.loads(Path("失敗原証拠索引.json").read_text())
a = m["checkpoints"][1]["archive"]
for p in a["parts"]:
    b = Path(p["path"]).read_bytes()
    assert len(b) == p["bytes"] and hashlib.sha256(b).hexdigest() == p["sha256"]
h = hashlib.sha256()
n = 0
with Path(a["path"]).open("xb") as out:
    for p in a["parts"]:
        with Path(p["path"]).open("rb") as src:
            while b := src.read(1048576):
                out.write(b); h.update(b); n += len(b)
assert n == a["bytes"] and h.hexdigest() == a["sha256"]
```

既存出力がある場合はexclusive-createで停止する。結合中にI/O失敗した出力は成功扱いせず、削除・上書きしない。原成果本数はbyte完全再構成可能なarchive単位で数え、part数を成果数にしない。
