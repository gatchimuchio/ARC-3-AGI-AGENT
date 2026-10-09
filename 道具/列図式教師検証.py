"""公開教師の取り込み/保持評価CLI。runtimeには原票path・解答・評価を渡さない。"""
import argparse,json,hashlib,sys
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'HDS/学習系統/v0.4.2'))
from hds学習系統 import HDS学習系統,外部入力
from 接続.図式観測 import _作用番号
from 接続.列図式規則 import (図式を観測する,一致する,照会,役割境界,目標境界,作用境界,
                           選択を読む,候補を構成する,候補台帳を構成する)
import itertools


def 公開原票を読む(path,digest):
    raw=Path(path).read_bytes();actual=hashlib.sha256(raw).hexdigest()
    if actual!=digest:raise ValueError('公開原票SHA256不一致')
    items=[json.loads(s) for s in raw.decode().splitlines() if s.strip()]
    return [item.get('data',item) for item in items]


def 完了数(row):
    if 'score'in row and 'levels_completed'in row and row['score']!=row['levels_completed']:raise ValueError('公開level新旧項目の矛盾')
    v=row.get('levels_completed',row.get('score'))
    if type(v)is not int or v<0:raise ValueError('公開完了数欠損/不正')
    return v


def 同一実行(a,b):
    return bool(a.get('game_id') and a.get('guid') and (a['game_id'],a['guid'])==(b.get('game_id'),b.get('guid')))


def 記号記録(item):return {'位置':item['位置'],'色':item['記号']['色'],'中空':item['記号']['中空']}


def 遷移作用を測る(before,after,action,advanced):
    try:a=図式を観測する(before)
    except ValueError as e:return {'状態':'HOLD','理由':str(e)}
    number=_作用番号(action['id'])
    if advanced:return {'状態':'実測','作用':'完成列提出','行動ID':number,'観測':'公開完了数増加'}
    try:b=図式を観測する(after);selected_a=選択を読む(before,a);selected_b=選択を読む(after,b)
    except ValueError as e:return {'状態':'HOLD','理由':str(e)}
    aa={tuple(s['位置']):s['記号'] for z in a['容器群'] for s in z['枠群']};bb={tuple(s['位置']):s['記号'] for z in b['容器群'] for s in z['枠群']}
    if aa.keys()!=bb.keys():return {'状態':'HOLD','理由':'スロット構造変化'}
    changed=[xy for xy in aa if aa[xy]!=bb[xy]];data=action.get('data',{});point=(data.get('x'),data.get('y'))
    def hit(xy,margin=0):return type(point[0])is int and type(point[1])is int and xy[0]-margin<=point[0]<xy[0]+4+margin and xy[1]-margin<=point[1]<xy[1]+4+margin
    if len(changed)==1 and aa[changed[0]] is None and selected_a and bb[changed[0]]==selected_a['記号'] and len(a['在庫群'])==len(b['在庫群'])+1 and hit(changed[0],1):
        return {'状態':'実測','作用':'選択記号を空欄へ割当','行動ID':number,'対象位置':list(changed[0]),'選択記号':記号記録(selected_a),'観測':'選択記号と一致する1スロット充填、在庫1減少'}
    if not changed and selected_b and selected_a!=selected_b and hit(selected_b['位置'],1) and a['在庫群']==b['在庫群']:
        return {'状態':'実測','作用':'在庫記号を選択','行動ID':number,'選択記号':記号記録(selected_b),'観測':'在庫外周選択表示、スロット不変、在庫数不変'}
    if before==after:return {'状態':'可視変化なし','行動ID':number,'注意':'hidden state不変は断定しない'}
    return {'状態':'HOLD','理由':'観測した作用語彙に未一致','変化スロット数':len(changed),'在庫数差':len(b['在庫群'])-len(a['在庫群'])}


def 教師を取り込む(系,原票,完成行群,目標範囲群,作用範囲群,*,原票SHA256):
    """一つの外部HDSに全教師を投入。IDは由来確認専用で解法選択に使わない。"""
    records=[];completed=[];submit_ids=set()
    def provenance(i,frame):return {'原票SHA256':原票SHA256,'行':i,'応答frame':frame}
    for i in 完成行群:
        if not 1<=i<len(原票):raise ValueError('完成教師行の範囲不正')
        before,after=原票[i-1],原票[i]
        if not 同一実行(before,after) or after.get('full_reset') or 完了数(after)!=完了数(before)+1 or not after.get('frame'):raise ValueError('公開成功遷移で裏付けられない完成教師')
        completed.append((i,図式を観測する(after['frame'][0])));submit_ids.add(_作用番号(after['action_input']['id']))
    if len(submit_ids)!=1:raise ValueError('公開成功に先行する提出作用を一意に観測できない')
    semantic=[dict(zip((False,True),ops)) for ops in itertools.product(('出力','参照'),repeat=2)]
    for i,scene in completed:semantic=[r for r in semantic if 一致する(scene,r)[0]]
    if len(semantic)!=1:raise ValueError('完成見本から固定役割語彙の意味を一意に誘導できない')
    roles=semantic[0]
    for i,scene in completed:
        for box in scene['容器群']:
            for slot in box['枠群']:
                token=slot['記号'];facts={'記号は中空':token['中空'],'列展開役割':roles[token['中空']]};r=系.処理する(外部入力(facts,役割境界));records.append({'種別':'役割教師','出所':provenance(i,0),'位置':slot['位置'],'教師':facts,'経験参照':r.追跡情報.get('経験参照')})
    learned={}
    for hollow in (False,True):learned[hollow],_=照会(系,役割境界,{'記号は中空':hollow},'列展開役割')
    if any(v is None for v in learned.values()):raise ValueError('HDS役割照会が未成立')
    used=set()
    for start,end in 目標範囲群:
        if not 1<=start<=end<len(原票):raise ValueError('目標教師範囲不正')
        for i in range(start,end+1):
            if i in used:raise ValueError('重複する目標教師範囲')
            used.add(i);before,after=原票[i-1],原票[i]
            if not after.get('action_input') or _作用番号(after['action_input']['id']) not in submit_ids:continue
            origin=provenance(i,-1)
            if not 同一実行(before,after) or after.get('full_reset') or not before.get('frame'):records.append({'種別':'HOLD','出所':origin,'理由':'instance/reset/frame境界'});continue
            match,detail=一致する(図式を観測する(before['frame'][-1]),learned);accepted=完了数(after)>完了数(before)
            if detail.get('構造状態')=='HOLD':records.append({'種別':'HOLD','出所':origin,'理由':detail['理由'],'実提出受理':accepted,'目標教師使用':False});continue
            facts={'終端条件に応じた列が一致':match,'提出が受理された':accepted};r=系.処理する(外部入力(facts,目標境界));records.append({'種別':'目標教師','出所':origin,'教師':facts,'生成観測':detail,'経験参照':r.追跡情報.get('経験参照')})
    used=set()
    for start,end in 作用範囲群:
        if not 1<=start<=end<len(原票):raise ValueError('作用教師範囲不正')
        for i in range(start,end+1):
            if i in used:raise ValueError('重複する作用教師範囲')
            used.add(i);before,after=原票[i-1],原票[i];origin=provenance(i,-1)
            if not 同一実行(before,after) or after.get('full_reset') or not before.get('frame') or not after.get('frame') or not after.get('action_input'):records.append({'種別':'作用HOLD','出所':origin,'理由':'instance/reset/frame/action境界'});continue
            number=_作用番号(after['action_input']['id']);available={_作用番号(v) for v in before.get('available_actions',[])}
            if number not in available:records.append({'種別':'作用HOLD','出所':origin,'理由':'前観測の利用可能作用にない'});continue
            measurement=遷移作用を測る(before['frame'][-1],after['frame'][-1],after['action_input'],完了数(after)>完了数(before));record={'種別':'作用観測','出所':origin,'実測':measurement}
            if measurement['状態']=='実測':
                facts={'解答作業':measurement['作用'],'必要行動ID':measurement['行動ID']};r=系.処理する(外部入力(facts,作用境界));record.update({'教師':facts,'経験参照':r.追跡情報.get('経験参照')})
            records.append(record)
    return {'教師記録':records,'残存意味候補':[{'中空' if k else '塗り潰し':v for k,v in roles.items()}],'完成教師行':list(完成行群),'提出作用の公開観測':sorted(submit_ids),'注意':'意味候補誘導/知覚/列解釈/探索は固定。HDSは与えられた対応を取得。'}


def 評価する(系,原票,問題行群,解答行群,*,原票SHA256):
    if len(問題行群)!=len(解答行群):raise ValueError('問題/解答行数不一致')
    result=[]
    for start,end in zip(問題行群,解答行群):
        if not 0<=start<end<len(原票):raise ValueError('問題/解答行範囲不正')
        problem=原票[start];out=候補を構成する(系,problem['frame'][-1],作用可能番号=[_作用番号(v) for v in problem['available_actions']],出所={'原票SHA256':原票SHA256,'問題行':start,'応答frame':-1})
        # Runtime has returned before the completed answer is read for scoring.
        if 完了数(原票[end])!=完了数(原票[end-1])+1 or not 同一実行(problem,原票[end]):raise ValueError('評価解答の公開成功/同一実行が不成立')
        answer=図式を観測する(原票[end]['frame'][0]);lookup={tuple(s['位置']):s['記号'] for b in answer['容器群'] for s in b['枠群']}
        exact=any(all(lookup[tuple(x['位置'])]=={'色':x['色'],'中空':x['中空']} for x in sol['割当']) for sol in out['目標候補群'])
        result.append({'問題行':start,'事後照合完成行':end,'結果':out,'公開完成割当を候補集合に含む':exact,'台帳':候補台帳を構成する(out)})
    return result


def _範囲(text):
    a,b=map(int,text.split(':'));return a,b

def _保存(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2))

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    for name in ('train','evaluate','extract-problem'):
        q=sub.add_parser(name);q.add_argument('--recording',required=True);q.add_argument('--sha256',required=True);q.add_argument('--output',required=True)
        if name=='train':q.add_argument('--answer-rows',type=int,nargs='+',required=True);q.add_argument('--goal-ranges',type=_範囲,nargs='+',required=True);q.add_argument('--action-ranges',type=_範囲,nargs='+',required=True);q.add_argument('--memory',required=True)
        elif name=='evaluate':q.add_argument('--memory',required=True);q.add_argument('--problem-rows',type=int,nargs='+',required=True);q.add_argument('--answer-rows',type=int,nargs='+',required=True)
        else:q.add_argument('--row',type=int,required=True)
    q=sub.add_parser('infer');q.add_argument('--memory',required=True);q.add_argument('--problem',required=True);q.add_argument('--available-actions',type=int,nargs='+',required=True);q.add_argument('--output',required=True)
    a=p.parse_args()
    if a.command=='infer':out=候補を構成する(HDS学習系統.読み込む(a.memory),json.loads(Path(a.problem).read_text()),作用可能番号=a.available_actions);_保存(a.output,out);return
    rows=公開原票を読む(a.recording,a.sha256)
    if a.command=='train':
        h=HDS学習系統();out=教師を取り込む(h,rows,a.answer_rows,a.goal_ranges,a.action_ranges,原票SHA256=a.sha256);h.保存する(a.memory);_保存(a.output,out)
    elif a.command=='evaluate':_保存(a.output,評価する(HDS学習系統.読み込む(a.memory),rows,a.problem_rows,a.answer_rows,原票SHA256=a.sha256))
    else:_保存(a.output,rows[a.row]['frame'][-1])
if __name__=='__main__':main()
