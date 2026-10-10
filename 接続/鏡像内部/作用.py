import copy,ast
from . import 基礎 as e
def effect(hyp,axes,action,hds):
 def query(f,b,k):return e.ask(hds,f,b,k)
 parts=hyp['構成群'];role,idx=hyp['選択対応'];act=action['id'];ax=copy.deepcopy(axes);q=[];outs=[]
 if act in e.D:
  sc={'選択':{'役割':'本体','対象':{'点':parts[idx]}}if role=='本体'else{'役割':'鏡軸','対象':ax[idx]}}
  facts=e.facts(sc,act);qq=query(e.encode(facts,True),e.MOVE,'実測局所変位');q.append(qq)
  if qq['値']is None:return {'HOLD':'局所作用未支持','照会':q}
  dx,dy=ast.literal_eval(qq['値']);new=list(parts)
  if role=='本体':new[idx]=frozenset((x+dx,y+dy)for x,y in parts[idx])
  else:ax[idx]['位置']+=(dx,dy)[ax[idx]['方向']]
  outs=[{'構成群':tuple(new),'選択対応':(role,idx),'軸':ax}]
 elif act==6:
  point=(action['data']['x']//3,action['data']['y']//3);clicked=[i for i,p in enumerate(parts)if point in p]
  if not clicked:return {'HOLD':'未学習クリック包含外','照会':[]}
  for i in clicked:
   f={'対象役割':'本体','クリック包含':True,'前選択':role=='本体'and i==idx,'クリックは選択可能領域':True};qq=query(e.encode(f,True),e.SELECT,'後選択');q.append(qq)
   if qq['値']is not True:return {'HOLD':'本体選択未支持','照会':q}
   outs.append({'構成群':parts,'選択対応':('本体',i),'軸':ax})
 elif act==5:
  if role!='鏡軸':return {'HOLD':'本体からの選択循環は未学習','照会':[]}
  f={'現選択軸方向':ax[idx]['方向'],'可動軸数':sum(a['可動']for a in ax)};qq=query(e.encode(f,True),'公開鏡像:軸からの選択循環','後選択役割');q.append(qq)
  if qq['値']is None:return {'HOLD':'軸循環未支持','照会':q}
  if qq['値']=='本体':outs=[{'構成群':parts,'選択対応':('本体',i),'軸':ax}for i in range(len(parts))]
  elif qq['値'].startswith('軸方向'):
   indices=[i for i,a in enumerate(ax)if a['方向']==int(qq['値'][-1])];outs=[{'構成群':parts,'選択対応':('鏡軸',i),'軸':ax}for i in indices]
  else:return {'HOLD':'循環後役割が語彙外','照会':q}
 else:return {'HOLD':'未学習作用','照会':[]}
 outputs=[]
 B=set().union(*parts);C=e.visible(e.orbit(B,axes))-B
 for out in outs:
  NB=set().union(*out['構成群']);NC=e.visible(e.orbit(NB,out['軸']))-NB;nr,ni=out['選択対応'];sel={'役割':nr,'点':sorted(out['構成群'][ni])}if nr=='本体'else{'役割':nr,'方向':out['軸'][ni]['方向'],'位置':out['軸'][ni]['位置']}
  outputs.append({'次仮説':out,'効果':{'本体追加':NB-B,'本体除去':B-NB,'複製追加':NC-C,'複製除去':C-NC,'次軸':[(a['方向'],a['位置'])for a in out['軸']],'次選択対応':sel}})
 return {'照会':q,'候補':outputs}
