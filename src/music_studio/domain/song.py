from .section import SongError, text, validate_section
from ..music import validate_settings

def validate_song(value):
    if not isinstance(value, dict) or value.get('schema_version') != 2:
        raise SongError('Song schema_version 2가 필요합니다.', 'schema_version')
    title = text(value.get('title'), 'title', 160)
    sections = value.get('sections')
    if not isinstance(sections, list) or len(sections) > 64:
        raise SongError('Section은 최대 64개입니다.', 'sections')
    sections = [validate_section(s) for s in sections]
    if len({s['id'] for s in sections}) != len(sections):
        raise SongError('Section ID는 중복될 수 없습니다.', 'id')
    if sum(len('\n'.join(s['lyrics'])) for s in sections) > 12000:
        raise SongError('전체 가사는 12,000자 이하여야 합니다.', 'lyrics')
    settings = validate_settings(value.get('music_settings'))
    return dict(schema_version=2, title=title, sections=sections, music_settings=settings)
