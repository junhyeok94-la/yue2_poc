import json
import unittest
import test_web
from music_studio import cli, web

class LibraryManagementTests(unittest.TestCase):
    setUp=test_web.WebTests.setUp
    tearDown=test_web.WebTests.tearDown
    request=test_web.WebTests.request

    def test_rename_persists_without_rewriting_generation_input(self):
        original=(self.folder/'metadata.json').read_bytes()
        code,_,body=self.request('POST','/api/tracks/rename',{'id':self.run_id,'title':'  새 이름 🎵  '})
        self.assertEqual(code,200)
        self.assertEqual(json.loads(body)['title'],'새 이름 🎵')
        self.assertEqual((self.folder/'metadata.json').read_bytes(),original)
        reopened=web.Studio(self.config,self.root)
        self.assertEqual(reopened.library()[0]['title'],'새 이름 🎵')
        self.assertEqual(reopened.library()[0]['input']['title'],self.data['title'])

    def test_delete_restore_preserve_audio_metadata_and_name(self):
        original=(self.folder/'metadata.json').read_bytes()
        audio=(self.folder/'audio.wav').read_bytes()
        self.request('POST','/api/tracks/rename',{'id':self.run_id,'title':'복원할 곡'})
        self.studio.job=dict(id='done',status='succeeded',run_id=self.run_id)
        self.assertEqual(self.request('POST','/api/tracks/delete',{'id':self.run_id})[0],200)
        state=json.loads(self.request('GET','/api/state')[2])
        self.assertEqual(state['tracks'],[])
        self.assertEqual(state['trash'][0]['title'],'복원할 곡')
        self.assertIsNone(state['job'])
        self.assertEqual(self.request('GET','/api/audio?id='+self.run_id)[0],404)
        self.assertEqual(self.request('POST','/api/replay',{'id':self.run_id})[0],400)
        self.assertEqual(len(web.Studio(self.config,self.root).library(deleted=True)),1)
        self.assertEqual(self.request('POST','/api/tracks/restore',{'id':self.run_id})[0],200)
        state=json.loads(self.request('GET','/api/state')[2])
        self.assertEqual(state['trash'],[])
        self.assertEqual(state['tracks'][0]['title'],'복원할 곡')
        self.assertTrue(state['tracks'][0]['has_audio'])
        self.assertEqual((self.folder/'metadata.json').read_bytes(),original)
        self.assertEqual((self.folder/'audio.wav').read_bytes(),audio)

    def test_invalid_names_paths_and_origin(self):
        for title in ['', ' ', 'x'*161, 'a\nb', None]:
            self.assertEqual(self.request('POST','/api/tracks/rename',{'id':self.run_id,'title':title})[0],400)
        self.assertEqual(self.request('POST','/api/tracks/delete',{'id':'../../outside'})[0],400)
        self.assertEqual(self.request('POST','/api/tracks/delete',{'id':self.run_id},{'Origin':'https://example.org'})[0],403)
        self.assertFalse((self.folder/'library.json').exists())

    def test_running_and_cli_lock_block_changes(self):
        for action in ('rename','delete','restore'):
            self.studio.job={'status':'running'}
            self.assertEqual(self.request('POST','/api/tracks/'+action,{'id':self.run_id,'title':'new'})[0],409)
        self.studio.job=None
        (self.root/'.generation.lock').write_text('123')
        self.assertEqual(self.request('POST','/api/tracks/delete',{'id':self.run_id})[0],409)
        (self.root/'.generation.lock').unlink()
        meta=cli.read_json(self.folder/'metadata.json');meta['status']='running';cli.save_json(self.folder/'metadata.json',meta)
        self.assertEqual(self.request('POST','/api/tracks/delete',{'id':self.run_id})[0],409)
        self.assertFalse((self.folder/'library.json').exists())
