import re
import uuid
from .compiler import HEADERS

def import_lyrics(lyrics):
    sections, current = [], None
    for line in lyrics.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        match = re.fullmatch(r'\[([^\[\]]+)\]', line.strip())
        if match:
            label = match[1]
            kind = next((k for k, name in HEADERS.items() if re.fullmatch(re.escape(name) + r'(?:\s+\d+)?', label, re.I)), 'custom')
            current = dict(id=str(uuid.uuid4()), type=kind, label=label, bars=None, lyrics=[])
            sections.append(current)
            if kind == 'custom':
                current['lyrics'].append(line)
        else:
            if current is None:
                current = dict(id=str(uuid.uuid4()), type='custom', label='원문', bars=None, lyrics=[])
                sections.append(current)
            current['lyrics'].append(line)
    return sections
