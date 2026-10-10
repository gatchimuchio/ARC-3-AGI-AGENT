"""全完成候補ごとの軸→本体手順。最短/全軌跡探索ではない。"""
import json,itertools,copy
from . import 基礎 as e
CYCLE='公開鏡像:軸からの選択循環';D4='公開鏡像:可視性別D4候補'
def 手順を作る(h,initial,avail,目標候補):
 qcache={};plans=[];dq=[]
 def ask(f,b,k):
  key=json.dumps([f,b,k],sort_keys=True,ensure_ascii=False)
  if key not in qcache:qcache[key]=e.ask(h,f,b,k)
  return qcache[key]
 for rot,mir in itertools.product(range(4),(False,True)):
  f={'軸基準D4候補':f'法線反転={mir};四分回転={rot}','複製可視':bool(initial['複製'])};dq.append(ask(e.encode(f,True),D4,'複製と観測整合'))
 for goal in 目標候補['候補']:
  for displacements in itertools.product(*goal['対象全変位類']):
   objects=[set(o['点'])for o in initial['対象']];axes=copy.deepcopy(initial['軸']);selected=None
   if initial['選択']:
    ss=initial['選択'];selected=('軸',next(i for i,a in enumerate(axes)if a['方向']==ss['対象']['方向']))if ss['役割']=='鏡軸'else('本体',next(i for i,o in enumerate(initial['対象'])if o['点']==ss['対象']['点']))
   steps=[];holds=[]
   if initial['不明']:holds.append('知覚文法外')
   supported_ops=[q['入力']['前提直積']for q in dq if q['値']is True]
   if len(supported_ops)>1:holds.append('画面外空像で複数D4が観測同値。最初の可視化後に候補集合を再照会し、唯一性を仮定しない')
   if len(axes)>1:holds.append('二軸の鏡映合成は固定演算と公開実測整合に条件付き。HDS単軸作用意味の自動発見とは別')
   def scene_symbolic():
    sc={'軸':axes,'本体':set().union(*objects),'対象':[{'点':o,'選択':selected==('本体',i)}for i,o in enumerate(objects)],'選択':None}
    if selected:sc['選択']={'役割':'本体','対象':sc['対象'][selected[1]]}if selected[0]=='本体'else{'役割':'鏡軸','対象':axes[selected[1]]}
    return sc
   def allchoices():
    sc=scene_symbolic();out=[]
    for act in avail:
     if act in e.D:
      f=e.facts(sc,act);out.append({'id':act,'前提':f,'照会':ask(e.encode(f,True),e.MOVE,'実測局所変位')if f else None})
     elif act==6:out.append({'id':6,'全座標領域':{'x':list(range(64)),'y':list(range(64)),'積全数':4096},'採用範囲':'黒本体包含について照会。鏡軸クリックは未学習HOLD'})
     else:out.append({'id':act,'状態':'軸循環照会時のみ条件付き'if act==5 else'HOLD','理由':'回転/undo等の役割未同定を捨てない'})
    return out
   def move(target,dx,dy):
    nonlocal selected
    for dim,amount in enumerate((dx,dy)):
     act=(4 if amount>0 else 3)if dim==0 else(2 if amount>0 else 1)
     for _ in range(abs(amount)):
      options=allchoices();q=next((a for a in options if a['id']==act),{}).get('照会');expect=e.D[act]
      step={'操作':'本体移動'if target[0]=='本体'else'鏡軸移動','対象':target,'作用':{'id':act,'data':{}},'全作用候補':options,'期待変位':expect,'実測':None,'実行許可':False,'照会':q,'各手後':'liveの再観測で同一対象・位置・鏡像・成功遷移・hidden観測可否を再確認'}
      if not q or q['値']!=str(expect):step['状態']='HOLD';holds.append('必要単位変位がHDSで支持されない');steps.append(step);return False
      step['状態']='支持された局所作用に条件付き';steps.append(step)
      if target[0]=='本体':objects[target[1]]={(x+expect[0],y+expect[1])for x,y in objects[target[1]]}
      else:axes[target[1]]['位置']+=expect[axes[target[1]]['方向']]
    return True
   # 現在選択中の軸を先に処理。二軸では水平→垂直の実測循環を照会する。
   axis_order=sorted(range(len(axes)),key=lambda i:0 if selected==('軸',i)else 1)
   halted=False
   for i in axis_order:
    d=goal['軸位置'][i]-axes[i]['位置']
    if not d:continue
    if selected!=('軸',i):
     if selected and selected[0]=='軸':
      cur=axes[selected[1]];f={'現選択軸方向':cur['方向'],'可動軸数':sum(a['可動']for a in axes)};q=ask(e.encode(f,True),CYCLE,'後選択役割');expect='軸方向'+str(axes[i]['方向']);steps.append({'操作':'選択軸を循環','作用':{'id':5,'data':{}},'全作用候補':allchoices(),'照会':q,'期待選択':expect,'実行許可':False})
      if 5 not in avail or q['値']!=expect:holds.append('必要軸への選択経路が未学習');halted=True;break
      selected=('軸',i)
     else:holds.append('本体から必要軸への選択経路が未学習');halted=True;break
    delta=[0,0];delta[axes[i]['方向']]=d
    if not move(('軸',i),*delta):halted=True;break
   if not halted:
    for i,(dx,dy)in enumerate(displacements):
     if not dx and not dy:continue
     if selected!=('本体',i):
      # 全クリック同値座標を保持。対象重複部分は同一性が証明できないため候補保留。
      others=set().union(*(o for j,o in enumerate(objects)if j!=i));unique=objects[i]-others;coords=sorted((3*x+xx,3*y+yy)for x,y in unique for xx in range(3)for yy in range(3));f={'対象役割':'本体','クリック包含':True,'前選択':False,'クリックは選択可能領域':True};q=ask(e.encode(f,True),e.SELECT,'後選択');step={'操作':'本体を包含クリックで選択','対象':['本体',i],'全同値クリック座標':coords,'曖昧重複セル':objects[i]&others,'全作用候補':allchoices(),'照会':q,'実行許可':False}
      if 6 not in avail or not coords or q['値']is not True:step['状態']='HOLD';holds.append('必要本体を選択する支持/座標がない');steps.append(step);halted=True;break
      step['代表作用']={'id':6,'data':{'x':coords[0][0],'y':coords[0][1]}};step['代表選択理由']='同一対象包含で観測上同値な全座標を保持した辞書順代表。最適化や候補剪定ではない';steps.append(step);selected=('本体',i)
     if not move(('本体',i),dx,dy):halted=True;break
   predicted=e.visible(e.orbit(set().union(*objects),axes));covered=initial['目標']<=predicted
   plans.append({'完成候補':{'軸位置':goal['軸位置'],'本体変位':displacements},'具体手順':steps,'具体操作数':len(steps),'最後まで具体化':not halted,'モデル上全黄目標被覆':covered,'条件':holds+['未実行。各作用後の観測が予測と違えば停止/HOLD。色/HUD/不可視状態の不変性は主張しない。'],'実行許可':False,'全順序の表現':'各本体のx/y単位移動の全順列は可換モデル上の同値類として保持。表示はx先行代表。状態境界/観測差は同値性を解除してHOLD。','全経路探索':'していない。遠回り/undo等は各段階の全作用候補に保持し、成功経路から排除したとは主張しない。'})
 return {'全完成配置に対する手順':plans,'D4候補照会':dq,'実行許可':False}
