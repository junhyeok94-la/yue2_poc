from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from music_studio import cli, web


class WebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run_id = '2026-09-23/123456-abcdef12'
        self.folder = self.root / self.run_id
        self.folder.mkdir(parents=True)
        self.data = dict(web.DEFAULTS, title='한강의 노래', style='Korean R&B', lyrics='[Verse]\n새벽의 노래')
        self.config = {'backend': 'cuda'}
        cli.save_json(self.folder / 'metadata.json', dict(id='123456-abcdef12', input=self.data,
                      config=self.config, status='succeeded', created_at='2026-09-23T12:00:00+09:00'))
        (self.folder / 'audio.wav').write_bytes(b'RIFF' + bytes(range(256)) * 4)
        self.release = threading.Event()
        self.finished = threading.Event()
        self.received = []
        def generator(config, data, root, parent_id, on_started):
            self.received.append((config, data, parent_id))
            on_started(self.folder)
            self.release.wait(5)
            return self.folder, {'status':'succeeded'}
        self.studio = web.Studio(self.config, self.root, generator)
        self.preflight = patch.object(cli, 'preflight', return_value=[])
        self.preflight.start()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), web.make_handler(self.studio))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.release.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.preflight.stop()
        self.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        h = {'Content-Type':'application/json', 'X-Studio-Request':'1'}
        h.update(headers or {})
        conn.request(method, path, json.dumps(body) if body is not None else None, h)
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def test_library_existing_outputs(self):
        code, _, body = self.request('GET', '/api/state')
        self.assertEqual(code, 200)
        state = json.loads(body)
        self.assertEqual(state['tracks'][0]['title'], '한강의 노래')
        self.assertTrue(state['tracks'][0]['has_audio'])

    def test_audio_ranges_head_and_download(self):
        path = '/api/audio?id=' + self.run_id
        code, headers, body = self.request('GET', path, headers={'Range':'bytes=0-3'})
        self.assertEqual((code, body), (206, b'RIFF'))
        self.assertEqual(headers['Content-Range'], 'bytes 0-3/1028')
        self.assertEqual(self.request('GET', path, headers={'Range':'bytes=-4'})[2], bytes(range(252,256)))
        self.assertEqual(self.request('GET', path, headers={'Range':'bytes=9999-'})[0], 416)
        self.assertEqual(self.request('HEAD', path)[2], b'')
        self.assertIn('attachment', self.request('GET', path+'&download=1')[1]['Content-Disposition'])

    def test_rejects_cross_origin_and_path_escape(self):
        self.assertEqual(self.request('POST','/api/jobs',self.data,{'Origin':'https://example.org'})[0],403)
        self.assertEqual(self.request('POST','/api/jobs',self.data,{'X-Studio-Request':''})[0],403)
        self.assertEqual(self.request('GET','/api/state',headers={'Host':'example.org'})[0],403)
        self.assertEqual(self.request('GET','/api/audio?id=../../config/local.json')[0],400)
        self.assertEqual(self.request('GET','/config/local.json')[0],404)

    def test_single_worker_and_reconnect_state(self):
        code, _, body = self.request('POST','/api/jobs',self.data)
        self.assertEqual(code,202)
        job_id=json.loads(body)['id']
        self.assertEqual(self.request('POST','/api/jobs',self.data)[0],409)
        state=json.loads(self.request('GET','/api/state')[2])
        self.assertEqual(state['job']['id'],job_id)
        self.release.set()
        for _ in range(100):
            if self.studio.status()['status'] != 'running':break
            time.sleep(.01)
        self.assertEqual(self.studio.status()['status'],'succeeded')

    def test_replay_keeps_input_seed_and_parent(self):
        self.assertEqual(self.request('POST','/api/replay',{'id':self.run_id})[0],202)
        for _ in range(100):
            if self.received:break
            time.sleep(.01)
        self.assertEqual(self.received[0],(self.config,self.data,'123456-abcdef12'))

    def test_validation_and_worker_failure(self):
        bad=dict(self.data,lyrics=' ')
        self.assertEqual(self.request('POST','/api/jobs',bad)[0],400)
        self.assertIsNone(self.studio.job)
        def fail(*args,**kwargs):raise RuntimeError('test engine failure')
        self.studio.generator=fail
        self.assertEqual(self.request('POST','/api/jobs',self.data)[0],202)
        for _ in range(100):
            if self.studio.status()['status'] != 'running':break
            time.sleep(.01)
        self.assertEqual(self.studio.status()['status'],'failed')
        self.assertEqual(self.studio.status()['error'],'test engine failure')


if __name__=='__main__':unittest.main()
