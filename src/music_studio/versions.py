"""Read-only lineage projection for old replay metadata and new version records."""
from collections import defaultdict

KINDS = {'original':'Original', 'variation':'Variation', 'lyrics_revision':'Lyrics Revision', 'remix':'Remix', 'replay':'Replay', 'score_revision':'Score Revision'}

def annotate(tracks):
    by_id = {t['id']:t for t in tracks}
    short = defaultdict(list)
    for t in tracks: short[t['id'].split('/')[-1]].append(t['id'])
    for t in tracks:
        record=t.pop('_version', {})
        if not isinstance(record, dict): record={}
        legacy=t.pop('_legacy_parent', None)
        parent=record.get('parent_id') or legacy
        if not isinstance(parent, str): parent=None
        if parent and parent not in by_id and len(short.get(parent, []))==1: parent=short[parent][0]
        t['parent_id']=parent
        t['version_kind']=record.get('kind', 'replay' if parent else 'original')
        if not isinstance(t['version_kind'], str) or t['version_kind'] not in KINDS: t['version_kind']='variation'
    for t in tracks:
        path=[];current=t['id'];issue=None
        while current in by_id:
            if current in path:
                issue='순환된 버전 관계';current=min(path[path.index(current):]);break
            path.append(current)
            parent=by_id[current]['parent_id']
            if not parent:break
            if parent not in by_id:
                issue='원본 기록을 찾을 수 없습니다.'
                current='missing:'+parent;break
            current=parent
        t['song_id']=current
        t['lineage_issue']=issue
    return tracks

def compare(left, right):
    labels={'abc':'입력 ABC 악보','title':'곡 제목','lyrics':'가사','style':'최종 스타일','seed':'시드','steps':'합성 스텝','threads':'스레드','timeout':'제한 시간','cot':'내부 계획 모드'}
    result=[]
    for key,label in labels.items():
        a=left['input'].get(key);b=right['input'].get(key)
        if a!=b:result.append(dict(field=key,label=label,before=a,after=b))
    for key,label in [('sections','곡 구조'),('music_settings','음악 설정')]:
        def value(meta):
            data=meta['input'];song=data.get('song',{})
            return song.get(key) if key=='sections' else song.get(key,data.get(key))
        a=value(left);b=value(right)
        if a!=b:result.append(dict(field=key,label=label,before=a,after=b))
    if left.get('config')!=right.get('config'):
        result.append(dict(field='config',label='생성 엔진 설정',before=left.get('config'),after=right.get('config')))
    return result
