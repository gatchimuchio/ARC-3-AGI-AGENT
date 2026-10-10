"""core不変。既存永続化._符号化と同形式を一段ずつ展開してJSON iteratorへ渡す。
使用前に通常core保存と平文SHAが一致することを検証する。学習/採否/精度を変更しない。
"""
import dataclasses,enum,json,gzip,hashlib,os,tempfile,shutil,time
from pathlib import Path
class 遅延値:
 def __init__(self,value):self.value=value
class 同形式JSON(json.JSONEncoder):
 def default(self,obj):
  if not isinstance(obj,遅延値):return super().default(obj)
  x=obj.value
  if isinstance(x,enum.Enum):return {'__列挙__':type(x).__name__,'値':x.value}
  if dataclasses.is_dataclass(x):return {'__データ型__':type(x).__name__,'値':{f.name:遅延値(getattr(x,f.name))for f in dataclasses.fields(x)}}
  if isinstance(x,tuple):return {'__組__':[遅延値(v)for v in x]}
  if isinstance(x,list):return [遅延値(v)for v in x]
  if isinstance(x,dict):return {'__辞書__':[[遅延値(k),遅延値(v)]for k,v in x.items()]}
  return x

def 全内容(h):
 e=h.エンジン
 return {'形式版':3,'最小支持数':e.最小支持数,'最大条件数':e.最大条件数,'識別子状態':e.識別子.状態を書き出す(),'台帳':e.台帳.全取得(),'状態履歴':e.状態.履歴(),'原理履歴':e._原理履歴}

