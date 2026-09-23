from copy import deepcopy

TYPES = ('intro', 'verse', 'pre_chorus', 'chorus', 'post_chorus', 'bridge',
         'breakdown', 'outro', 'instrumental', 'custom')

class SongError(ValueError):
    def __init__(self, message, field=None, section_id=None):
        super().__init__(message)
        self.field, self.section_id = field, section_id

def text(value, field, limit, section_id=None):
    if not isinstance(value, str) or '\0' in value or len(value) > limit:
        raise SongError(f'{field}: {limit}자 이하의 텍스트가 필요합니다.', field, section_id)
    return value

def validate_section(value):
    if not isinstance(value, dict):
        raise SongError('Section 형식이 올바르지 않습니다.')
    sid = text(value.get('id'), 'id', 80)
    if not sid.strip():
        raise SongError('Section ID가 필요합니다.', 'id')
    if value.get('type') not in TYPES:
        raise SongError('알 수 없는 Section 타입입니다.', 'type', sid)
    text(value.get('label'), 'label', 80, sid)
    bars = value.get('bars')
    if bars is not None and (type(bars) is not int or not 1 <= bars <= 128):
        raise SongError('마디 수는 미정 또는 1~128 정수로 입력하세요.', 'bars', sid)
    lines = value.get('lyrics')
    if not isinstance(lines, list) or len(lines) > 12000:
        raise SongError('가사는 행 배열이어야 합니다.', 'lyrics', sid)
    for line in lines:
        text(line, 'lyrics', 12000, sid)
        if '\n' in line or '\r' in line:
            raise SongError('배열의 각 항목은 한 행이어야 합니다.', 'lyrics', sid)
    if len('\n'.join(lines)) > 12000:
        raise SongError('Section 가사가 너무 깁니다.', 'lyrics', sid)
    return deepcopy({k: value[k] for k in ('id', 'type', 'label', 'lyrics')} | {'bars': bars})
