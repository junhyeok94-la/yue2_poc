"""Minimal local configuration; never expose credentials to the client."""
import os
import re
from pathlib import Path

def gemini_settings(root):
    values = {}
    path = Path(root) / '.env'
    if path.is_file():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            name, value = line.split('=', 1)
            if name.strip() in ('GEMINI_API_KEY', 'GEMINI_MODEL'):
                values[name.strip()] = value.strip().strip('"\'')
    key = os.environ.get('GEMINI_API_KEY', values.get('GEMINI_API_KEY', '')).strip()
    model = os.environ.get('GEMINI_MODEL', values.get('GEMINI_MODEL', 'gemini-2.5-flash')).strip()
    if not re.fullmatch(r'gemini-[a-zA-Z0-9._-]+', model):
        raise ValueError('GEMINI_MODEL 형식이 올바르지 않습니다.')
    return key, model
