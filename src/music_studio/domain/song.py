from .section import SongError, text, validate_section

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
    settings = value.get('music_settings')
    if not isinstance(settings, dict) or set(settings) - {'advanced_prompt'}:
        raise SongError('현재는 advanced_prompt만 지원합니다.', 'music_settings')
    style = text(settings.get('advanced_prompt'), 'advanced_prompt', 2000)
    return dict(schema_version=2, title=title, sections=sections, music_settings={'advanced_prompt': style})
