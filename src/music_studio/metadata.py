from .music import compile_style
from .domain.song import validate_song
from .domain.section import SongError
from .lyrics.compiler import VERSION, compile_song
from .lyrics.analyzer import analyze_section

def preview(value):
    song = validate_song(value)
    compiled, warnings = compile_song(song)
    return dict(song=song, compiled_lyrics=compiled, compiler_version=VERSION, compiled_style=compile_style(song['music_settings']),
                analysis=[analyze_section(s) for s in song['sections']], warnings=warnings)

def generation_input(song):
    result = preview(song)
    if not result['compiled_lyrics'].strip():
        raise SongError('가사가 있는 Section을 하나 이상 작성하세요.', 'lyrics')
    song = result['song']
    return dict(title=song['title'], style=compile_style(song['music_settings']),
                lyrics=result['compiled_lyrics'], compiled_lyrics=result['compiled_lyrics'],
                compiler_version=VERSION, song=song)

def validate_snapshot(data):
    if 'song' not in data:
        if 'music_settings' in data and compile_style(data['music_settings']) != data.get('style'):
            raise SongError('음악 설정과 생성 스타일이 일치하지 않습니다.')
        return
    song = validate_song(data['song'])
    if (data.get('compiled_lyrics') != data.get('lyrics') or
            type(data.get('compiler_version')) is not int or data['compiler_version'] < 1 or
            song['title'] != data.get('title') or compile_style(song['music_settings']) != data.get('style')):
        raise SongError('저장된 Song과 생성 입력이 일치하지 않습니다.')

def read_input(meta):
    if meta.get('schema_version', 1) not in (1, 2):
        raise SongError('지원하지 않는 metadata 버전입니다.')
    data = meta['input']
    if meta.get('schema_version') == 2 and 'song' not in data:
        raise SongError('v2 metadata에 Song이 없습니다.')
    validate_snapshot(data)
    return data
