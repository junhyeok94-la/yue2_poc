"""Isolated browser QA server; real generation, fixture audio is silence.
Run from the repository: python tests/manual_ui_fixture.py (port 7861).
Never use alongside another GPU generation job. Outputs stay under outputs/ux-qa.
"""
from pathlib import Path
from http.server import ThreadingHTTPServer
import sys
import wave
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from music_studio import cli, web
from music_studio.lyrics.gemini import GeminiAdvisor

TITLE = '새벽 두 시 한강을 달리며 오래전 헤어진 사람을 다시 떠올리는 이야기'
STYLE = 'Korean alternative R&B, warm nostalgic late-night atmosphere, soft intimate male vocal, electric piano, Rhodes, ambient synth pad, muted bass, brushed drums'
ABC = 'X:1\nM:4/4\nQ:1/4=90\nK:C\n' + 'C D E F | '.ljust(23960, 'C')

def main():
    root = cli.ROOT / 'outputs/ux-qa/library'
    config = cli.read_json(cli.ROOT / 'config/local.json')
    kinds = ['original','variation','lyrics_revision','score_revision','remix','variation']
    previous = None
    for i, kind in enumerate(kinds):
        run_id = f'2026-09-20/12000{i}-abcdef0{i}'
        folder = root / run_id
        folder.mkdir(parents=True, exist_ok=True)
        data = dict(web.DEFAULTS, title=TITLE + f' · fixture {i}', style=STYLE, lyrics='가사 한 줄\n' * 1700, cot='melody')
        cli.save_json(folder / 'metadata.json', dict(schema_version=1, id=folder.name, input=data, config=config, status='succeeded', created_at='2026-09-20T12:00:00+09:00', wav={'duration_seconds':2}, elapsed_seconds=1))
        cli.save_json(folder / 'version.json', dict(kind=kind,parent_id=previous))
        with wave.open(str(folder / 'audio.wav'), 'wb') as audio:
            audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(48000); audio.writeframes(bytes(192000))
        (folder / 'score.abc').write_text(ABC, encoding='utf-8')
        previous = run_id
    studio = web.Studio(config, root, advisor=GeminiAdvisor(''))
    server = ThreadingHTTPServer(('127.0.0.1',7861), web.make_handler(studio))
    print('Browser QA: http://127.0.0.1:7861/ - real GPU generation, isolated library', flush=True)
    server.serve_forever()

if __name__ == '__main__':
    main()

