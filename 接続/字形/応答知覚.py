"""909公開応答に使用した旧問題/全相の知覚分類を再利用。"""
import json
from .欄観測 import observe,可逆字形値
from .字形原語 import 字形群を読む
from .字形群制約 import 族値
SCOPE_X = '作用前にこの欄が選択されている'
SCOPE_Y = '応答先頭の同じ旧問題でこの欄の族ベクトルが変化'


def 境界(action):
    return '公開欄作用スコープ:族ベクトル変化:ACTION' + str(action)


def 可視欄(frame):
    cells, layout = {}, []
    for group in 字形群を読む(frame):
        x, y = group['位置']
        keys = []
        for j, glyph in enumerate(group['字形']):
            key = (x + 7 * j, y, group['色'])
            cells[key] = glyph
            keys.append(key)
        layout.append(tuple(keys))
    return cells, tuple(layout)


def 応答観測(previous_frame, frames, ref):
    before = observe(previous_frame)
    result = {**ref, '状態': 'HOLD', '全応答相': [], '欄観測': [], '保留理由群': []}
    if before['状態'] != '成立':
        result['保留理由群'].append('作用前の選択欄/役割/配置を一意に識別できない: ' + str(before.get('理由')))
        return result
    old_frames = []
    for index, frame in enumerate(frames):
        try:
            cells, layout = 可視欄(frame)
        except (TypeError,ValueError,IndexError,KeyError) as e:
            result['全応答相'].append({'相':index,'旧配置一致':False,'固定問題内容一致':False,'分類':'知覚例外・未確認','例外':type(e).__name__+': '+str(e)})
            result['保留理由群'].append({'相':index,'理由':'字形知覚を確認できない'})
            continue
        same_layout = layout == before['配置']
        same_fixed = same_layout and all(cells[k] == glyph for k, glyph in before['固定セル字形'])
        item = {'相': index, '旧配置一致': same_layout, '固定問題内容一致': same_fixed,
                '分類': '同じ旧問題' if same_fixed else '旧問題との対応不成立（次問題/演出/構文不一致）'}
        if same_fixed:
            families = [[族値(cells[k]) for k in field] for field in before['欄群']]
            exact = [[可逆字形値(cells[k]) for k in field] for field in before['欄群']]
            item['全欄族'] = families
            item['全欄実字形'] = exact
            old_frames.append((index, families, exact))
        result['全応答相'].append(item)
    if not old_frames or old_frames[0][0] != 0:
        result['保留理由群'].append('応答先頭frameを同じ旧問題として識別できない')
    if len({json.dumps(families) for _, families, _ in old_frames}) > 1:
        result['保留理由群'].append('同じ応答内の旧問題frameで族ベクトルが混在')
    if result['保留理由群']:
        return result
    after_family, after_exact = old_frames[0][1:]
    for field_index, field in enumerate(before['欄群']):
        bfamily = [族値(before['セル字形'][k]) for k in field]
        bexact = [可逆字形値(before['セル字形'][k]) for k in field]
        selected = field_index == before['選択欄']
        fchange = bfamily != after_family[field_index]
        echange = bexact != after_exact[field_index]
        result['欄観測'].append({'欄': field_index, '役割': '編集見本' if before['見本編集役割'] else '解答欄',
            '対象セル': field, '作用前選択欄': before['選択欄'],
            '教師': {SCOPE_X: selected, SCOPE_Y: fchange},
            '作用前族': bfamily, '作用後族': after_family[field_index],
            '作用前実字形': bexact, '作用後実字形': after_exact[field_index],
            '族変化': fchange, '実字形変化': echange,
            '成分ごとの族変化': [a != b for a, b in zip(bfamily, after_family[field_index])],
            '成分ごとの実字形変化': [a != b for a, b in zip(bexact, after_exact[field_index])],
            '選択と族変化の不一致観測': selected != fchange,
            '正解ラベル由来': '実観測before/応答先頭afterの族ベクトル比較。選択boolのコピーではない。'})
    result['状態'] = '観測成立'
    return result


