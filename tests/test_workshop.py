import copy
import json
from pathlib import Path
import sys
import unittest
import unicodedata
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from music_studio import cli, metadata
from music_studio.domain.song import validate_song
from music_studio.lyrics.compiler import compile_song, HEADERS
from music_studio.lyrics.analyzer import analyze_section
from music_studio.lyrics.importer import import_lyrics
import test_cli
import test_web

def song():
    return dict(schema_version=2, title='한강', music_settings={'advanced_prompt':'Korean R&B'},
                sections=[dict(id='a', type='verse', label='Verse 1', bars=8, lyrics=['새벽의 노래', '', '다시 노래']),
                          dict(id='b', type='chorus', label='후렴', bars=16, lyrics=['우리 함께'])])

class DomainTests(unittest.TestCase):
    def test_roundtrip_and_copy(self):
        original=song()
        result=validate_song(json.loads(json.dumps(original)))
        self.assertEqual(result,original)
        result['sections'][0]['lyrics'].append('변경')
        self.assertNotEqual(result,original)

    def test_compile_order_and_labels(self):
        value=song()
        self.assertEqual(compile_song(value)[0], '[Verse]\n새벽의 노래\n\n다시 노래\n\n[Chorus]\n우리 함께')
        value['sections'].reverse()
        self.assertTrue(compile_song(value)[0].startswith('[Chorus]'))
        self.assertNotIn('후렴',compile_song(value)[0])

    def test_all_headers_and_empty_sections(self):
        value=song()
        for kind,header in HEADERS.items():
            value['sections'][0]['type']=kind
            self.assertTrue(compile_song(value)[0].startswith('['+header+']'))
        value['sections'][0]['lyrics']=[]
        compiled,warnings=compile_song(value)
        self.assertEqual(compiled,'[Chorus]\n우리 함께')
        self.assertEqual(warnings[0]['section_id'],'a')
        value['sections'][1]['lyrics']=[' ']
        self.assertEqual(compile_song(value)[0],'')
        with self.assertRaises(ValueError):metadata.generation_input(value)

    def test_analysis_unicode_empty_and_mixed(self):
        s=dict(lyrics=['가나 hello 가나', '', ' ', 'hello 123', unicodedata.normalize('NFD','한글'), '🎵'])
        result=analyze_section(s|{'id':'a'})
        self.assertEqual(result['lines_count'],4)
        self.assertEqual(result['empty_lines'],2)
        self.assertEqual(result['approximate_syllables_per_line'],[4,None,None,None,2,None])
        self.assertEqual(result['average_syllables'],3)
        self.assertIn({'word':'가나','count':2},result['repeated_words'])
        self.assertEqual(s['lyrics'][-2],unicodedata.normalize('NFD','한글'))
        self.assertEqual(analyze_section({'id':'a','lyrics':[]})['line_length_variation']['stddev'],0)

    def test_validation_limits(self):
        for change in [dict(bars=True),dict(bars=0),dict(bars=129),dict(type='invalid'),dict(lyrics=['a\nb']),dict(id='')]:
            value=song();value['sections'][0].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):validate_song(value)
        value=song();value['sections'][1]['id']='a'
        with self.assertRaises(ValueError):validate_song(value)
        value=song();value['sections'][0]['lyrics']=['가'*12000];value['sections'][1]['lyrics']=[]
        with self.assertRaises(ValueError):compile_song(value)

    def test_import_preserves_unknown_and_blank_lines(self):
        sections=import_lyrics('앞말\r\n[Verse 1]\r\n한글\r\n\r\n[Special]\r\n끝')
        self.assertEqual([s['type'] for s in sections],['custom','verse','custom'])
        self.assertEqual(sections[1]['lyrics'],['한글',''])
        self.assertEqual(sections[2]['lyrics'],['[Special]','끝'])
        self.assertTrue(all(s['bars'] is None for s in sections))

    def test_snapshot_and_legacy_versions(self):
        data=metadata.generation_input(song())
        self.assertEqual(metadata.read_input({'schema_version':2,'input':data}),data)
        self.assertEqual(metadata.read_input({'input':{'lyrics':'original'}}),{'lyrics':'original'})
        with self.assertRaises(ValueError):metadata.read_input({'schema_version':2,'input':{'lyrics':'original'}})
        bad=copy.deepcopy(data);bad['lyrics']='changed'
        with self.assertRaises(ValueError):metadata.validate_snapshot(bad)
        # Replay accepts recorded text even if a future compiler would serialize differently.
        data['lyrics']=data['compiled_lyrics']='recorded exact text'
        metadata.validate_snapshot(data)

class WorkshopApiTests(unittest.TestCase):
    setUp=test_web.WebTests.setUp
    tearDown=test_web.WebTests.tearDown
    request=test_web.WebTests.request

    def test_preview_without_engine_and_guides(self):
        self.preflight.stop()
        code,_,body=self.request('POST','/api/song/preview',{'song':song()})
        self.assertEqual(code,200)
        self.assertIn('[Verse]',json.loads(body)['compiled_lyrics'])
        self.assertEqual(len(json.loads(self.request('GET','/api/workshop')[2])['types']),10)
        self.assertIsNone(self.studio.job)

    def test_new_generation_snapshot(self):
        payload={'song':song(),'seed':77}
        self.assertEqual(self.request('POST','/api/jobs',payload)[0],202)
        import time
        for _ in range(100):
            if self.received:break
            time.sleep(.01)
        data=self.received[0][1]
        self.assertEqual(data['song'],payload['song'])
        self.assertEqual(data['lyrics'],compile_song(payload['song'])[0])
        self.assertEqual(data['seed'],77)

    def test_ambiguous_and_invalid_requests(self):
        self.assertEqual(self.request('POST','/api/jobs',{'song':song(),'lyrics':'bad'})[0],400)
        bad=song();bad['sections'][0]['bars']=0
        code,_,body=self.request('POST','/api/song/preview',{'song':bad})
        self.assertEqual(code,400)
        self.assertEqual(json.loads(body)['section_id'],'a')
        self.assertEqual(self.request('POST','/api/song/preview',{'song':song()},{'Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.request('POST','/api/song/preview',{'padding':'x'*140000})[0],413)

    def test_v2_library_replay_and_legacy_unchanged(self):
        original=(self.folder/'metadata.json').read_bytes()
        new=self.root/'2026-09-24/123456-abcdef13';new.mkdir(parents=True)
        data=dict(self.data,**metadata.generation_input(song()))
        cli.save_json(new/'metadata.json',dict(schema_version=2,id='123456-abcdef13',input=data,
                      config=self.config,status='failed',created_at='2026-09-24T00:00:00+09:00'))
        tracks=json.loads(self.request('GET','/api/state')[2])['tracks']
        self.assertEqual({t['schema_version'] for t in tracks},{1,2})
        self.assertEqual((self.folder/'metadata.json').read_bytes(),original)
        self.assertEqual(self.request('POST','/api/replay',{'id':'2026-09-24/123456-abcdef13'})[0],202)
        import time
        for _ in range(100):
            if self.received:break
            time.sleep(.01)
        self.assertEqual(self.received[0][1],data)

    def test_import_endpoint(self):
        code,_,body=self.request('POST','/api/song/import',{'lyrics':'[Verse]\n한글'})
        self.assertEqual(code,200)
        self.assertEqual(json.loads(body)['sections'][0]['lyrics'],['한글'])

class SnapshotGenerationTests(unittest.TestCase):
    setUp=test_cli.GenerationTests.setUp
    valid_runner=staticmethod(test_cli.GenerationTests.valid_runner)

    def test_v2_saved_at_start_and_success(self):
        data=dict(self.data,**metadata.generation_input(song()))
        snapshots=[]
        folder,meta=cli.generate(self.config,data,self.root/'outputs',runner=self.valid_runner,
            on_started=lambda folder:snapshots.append(cli.read_json(folder/'metadata.json')))
        self.assertEqual(snapshots[0]['schema_version'],2)
        self.assertEqual(snapshots[0]['input']['song'],song())
        self.assertEqual(meta['status'],'succeeded')
        self.assertEqual(meta['command'][meta['command'].index('--text')+1],data['compiled_lyrics'])
        self.assertEqual((folder/'lyrics.txt').read_text(encoding='utf8'),data['lyrics'])

    def test_failure_keeps_song_and_cli_replay_keeps_compiled(self):
        data=dict(self.data,**metadata.generation_input(song()))
        folder,meta=cli.generate(self.config,data,self.root/'outputs',runner=lambda *args:7)
        self.assertEqual(meta['status'],'failed')
        self.assertEqual(meta['input']['song'],song())
        with patch.object(cli,'generate',return_value=(folder,{'status':'succeeded'})) as call:
            self.assertEqual(cli.main(['replay',str(folder/'metadata.json')]),0)
        self.assertEqual(call.call_args.args[1],data)
