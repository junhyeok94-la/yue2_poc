import json
import unittest
import test_web
from music_studio import cli, web, versions

class LineageTests(unittest.TestCase):
    def track(self,id,parent=None,record=None):
        return dict(id=id,_legacy_parent=parent,_version=record or {})
    def test_legacy_replay_branch_and_deleted_parent(self):
        tracks=[self.track('day/root'),self.track('day/replay','root'),self.track('day/edit',record={'parent_id':'day/replay','kind':'lyrics_revision'})]
        tracks[0]['deleted']=True
        versions.annotate(tracks)
        self.assertEqual({t['song_id'] for t in tracks},{'day/root'})
        self.assertEqual(tracks[1]['parent_id'],'day/root')
        self.assertEqual(tracks[2]['version_kind'],'lyrics_revision')
    def test_missing_ambiguous_and_cyclic_parents(self):
        tracks=[self.track('one/same'),self.track('two/same'),self.track('day/child','same'),self.track('day/a',record={'parent_id':'day/b'}),self.track('day/b',record={'parent_id':'day/a'})]
        versions.annotate(tracks)
        self.assertEqual(tracks[2]['song_id'],'missing:same')
        self.assertIsNotNone(tracks[2]['lineage_issue'])
        self.assertEqual(tracks[3]['song_id'],tracks[4]['song_id'])
        self.assertIn('순환',tracks[3]['lineage_issue'])
    def test_compare_inputs_and_engine(self):
        left={'input':{'title':'a','lyrics':'old','seed':1,'music_settings':{'bpm':82}},'config':{'model':'old'}}
        right={'input':{'title':'b','lyrics':'new','seed':2,'music_settings':{'bpm':90}},'config':{'model':'new'}}
        changes=versions.compare(left,right)
        self.assertEqual({c['field'] for c in changes},{'title','lyrics','seed','music_settings','config'})
        self.assertEqual(versions.compare(left,left),[])

class VersionApiTests(unittest.TestCase):
    setUp=test_web.WebTests.setUp
    tearDown=test_web.WebTests.tearDown
    request=test_web.WebTests.request

    def generator(self,config,data,root,parent_id,on_started):
        folder=root/'2026-09-24/123457-abcdef13';folder.mkdir(parents=True)
        meta=dict(id=folder.name,parent_id=parent_id,input=data,config=config,status='running',created_at='2026-09-24')
        cli.save_json(folder/'metadata.json',meta);on_started(folder)
        meta['status']='failed';cli.save_json(folder/'metadata.json',meta)
        return folder,meta

    def test_branch_persists_restart_failure_and_parent_unchanged(self):
        self.studio.generator=self.generator
        original=(self.folder/'metadata.json').read_bytes()
        payload=self.data|{'lyrics':'수정한 가사','version':{'parent_id':self.run_id,'kind':'lyrics_revision'}}
        self.assertEqual(self.request('POST','/api/jobs',payload)[0],202)
        for _ in range(100):
            if self.studio.status()['status']!='running':break
            test_web.time.sleep(.01)
        reopened=web.Studio(self.config,self.root)
        tracks=reopened.library()
        child=next(t for t in tracks if t['id']!=self.run_id)
        self.assertEqual(child['parent_id'],self.run_id)
        self.assertEqual(child['song_id'],self.run_id)
        self.assertEqual(child['version_kind'],'lyrics_revision')
        self.assertEqual(child['status'],'failed')
        self.assertEqual((self.folder/'metadata.json').read_bytes(),original)
        code,_,body=self.request('GET','/api/versions/compare?left='+self.run_id+'&right='+child['id'])
        self.assertEqual(code,200);self.assertEqual(json.loads(body)['changes'][0]['field'],'lyrics')
        self.request('POST','/api/tracks/delete',{'id':self.run_id})
        self.assertEqual(reopened.library()[0]['song_id'],self.run_id)
        self.request('POST','/api/tracks/restore',{'id':self.run_id})
        self.assertEqual(len(reopened.library()),2)

    def test_replay_preserves_input_and_records_full_parent(self):
        self.studio.generator=self.generator
        self.assertEqual(self.request('POST','/api/replay',{'id':self.run_id})[0],202)
        for _ in range(100):
            if self.studio.status()['status']!='running':break
            test_web.time.sleep(.01)
        child=next(t for t in self.studio.library() if t['id']!=self.run_id)
        self.assertEqual(child['input'],self.data)
        self.assertEqual(child['version_kind'],'replay')
        self.assertEqual(child['parent_id'],self.run_id)

    def test_rejects_bad_or_unavailable_source(self):
        for version in [None,{}, {'parent_id':'../../outside','kind':'variation'}, {'parent_id':self.run_id,'kind':'invalid'}, {'parent_id':self.run_id,'kind':'variation','song_id':'spoof'}]:
            self.assertEqual(self.request('POST','/api/jobs',self.data|{'version':version})[0],400)
        self.request('POST','/api/tracks/delete',{'id':self.run_id})
        self.assertEqual(self.request('POST','/api/jobs',self.data|{'version':{'parent_id':self.run_id,'kind':'remix'}})[0],400)
        self.request('POST','/api/tracks/restore',{'id':self.run_id})
        meta=cli.read_json(self.folder/'metadata.json');meta['status']='running';cli.save_json(self.folder/'metadata.json',meta)
        self.assertEqual(self.request('POST','/api/jobs',self.data|{'version':{'parent_id':self.run_id,'kind':'variation'}})[0],409)
        self.assertEqual(self.request('GET','/api/versions/compare?left=../../outside&right='+self.run_id)[0],400)
