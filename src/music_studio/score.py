"""Bounded ABC text handling; not a complete ABC parser or audio transcriber."""
import re

MAX_CHARS = 24000

def validate_abc(value):
    if not isinstance(value,str) or len(value)>MAX_CHARS or not value.strip():
        raise ValueError('ABC 악보는 1~24,000자로 입력하세요.')
    if any(ord(c)<32 and c not in '\n\r\t' for c in value):
        raise ValueError('ABC 악보에 사용할 수 없는 제어 문자가 있습니다.')
    if not re.search(r'^K:[ \t]*\S+',value,re.M):
        raise ValueError('ABC 악보에 K: 조성 헤더가 필요합니다.')
    if not any(line.strip() and not re.match(r'^(?:[A-Za-z]:|%)',line.strip()) for line in value.splitlines()):
        raise ValueError('ABC 악보의 음표 본문이 필요합니다.')
    return value

def inspect(value):
    validate_abc(value)
    headers={}
    for field in ('T','M','L','Q','K'):
        match=re.search(r'^'+field+r':[ \t]*(.+)$',value,re.M)
        if match:headers[field]=match.group(1).strip()
    return {'headers':headers,'characters':len(value),'notice':'헤더와 크기만 확인합니다. 완전한 ABC 문법·음악적 정확성은 검증하지 않습니다.'}

def read(folder):
    # Prefer submitted notation: it is the exact conditioning used by this run.
    for name,source in [('input.abc','provided'),('score.abc','generated')]:
        path=folder/name
        if path.is_file():
            resolved=path.resolve()
            if not resolved.is_relative_to(folder.resolve()):raise ValueError('잘못된 악보 경로입니다.')
            if path.stat().st_size>MAX_CHARS*4:raise ValueError('악보 파일이 허용 크기를 초과했습니다.')
            value=path.read_text(encoding='utf-8-sig')
            if len(value)>MAX_CHARS:raise ValueError('악보가 24,000자를 초과했습니다.')
            return {'abc':value,'source':source}
    return None
