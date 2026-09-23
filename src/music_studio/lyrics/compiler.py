from ..domain.song import validate_song
from ..domain.section import SongError

VERSION = 1
HEADERS = dict(intro='Intro', verse='Verse', pre_chorus='Pre-Chorus', chorus='Chorus',
               post_chorus='Post-Chorus', bridge='Bridge', breakdown='Breakdown',
               outro='Outro', instrumental='Instrumental', custom='Custom')

def compile_song(value):
    song = validate_song(value)
    blocks, warnings = [], []
    for section in song['sections']:
        if not any(line.strip() for line in section['lyrics']):
            warnings.append(dict(section_id=section['id'], message='빈 Section은 생성 텍스트에서 제외됩니다.'))
            continue
        if any(line.strip().startswith('[') and line.strip().endswith(']') for line in section['lyrics']):
            warnings.append(dict(section_id=section['id'], message='대괄호 행은 엔진이 구간 힌트로 해석할 수 있습니다.'))
        blocks.append('[' + HEADERS[section['type']] + ']\n' + '\n'.join(section['lyrics']))
    compiled = '\n\n'.join(blocks)
    if len(compiled) > 12000:
        raise SongError('구간 헤더 포함 최종 가사는 12,000자 이하여야 합니다.', 'lyrics')
    return compiled, warnings
