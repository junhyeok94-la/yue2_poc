import json
import unittest
from copy import deepcopy
import test_web
from music_studio import music, metadata, cli
from music_studio.lyrics.gemini import GeminiAdvisor, AdvisorError

SETTINGS = dict(genre='R&B', bpm=82, key='A minor', moods=['warm','nostalgic'], vocal='soft male vocal', instruments=['piano','bass'], advanced_prompt='Korean')
SONG = dict(schema_version=2,title='새벽',sections=[dict(id='s1',type='verse',label='Verse',bars=8,lyrics=['조용한 밤'])],music_settings=SETTINGS)
def reply(items, finish='STOP'):
    return {'candidates':[{'finishReason':finish,'content':{'parts':[{'text':json.dumps({'suggestions':items})}]}}]}
def item(**kw):
    return dict(field='bpm',original='82',suggested='90',reason='조금 더 경쾌한 흐름을 시도할 수 있습니다.') | kw

class MusicTests(unittest.TestCase):
    def test_compilation_and_legacy_snapshot(self):
        self.assertEqual(music.compile_style({'advanced_prompt':'  original  '}),'  original  ')
        self.assertEqual(music.compile_style(SETTINGS),'R&B, 82 BPM, A minor, warm, nostalgic, soft male vocal, piano, bass, Korean')
        before=deepcopy(SONG)
        data=metadata.generation_input(SONG)
        self.assertEqual(data['song'],SONG)
        self.assertEqual(data['style'],music.compile_style(SETTINGS))
        metadata.validate_snapshot(data)
        self.assertEqual(SONG,before)
        with self.assertRaises(ValueError): metadata.validate_snapshot(data|{'style':'mismatch'})
        old=deepcopy(SONG);old['music_settings']={'advanced_prompt':'old prompt'}
        self.assertEqual(metadata.generation_input(old)['style'],'old prompt')
        self.assertEqual(metadata.read_input({'input':{'style':'legacy'}})['style'],'legacy')

    def test_invalid_settings_and_combined_length(self):
        for field,value in [('bpm',True),('bpm',29),('bpm',301),('bpm','82'),('key','H major'),('genre',{}),('moods','warm'),('instruments',['a']*13),('moods',['']),('vocal','a\nb'),('unknown','value')]:
            with self.subTest(field=field,value=value):
                with self.assertRaises(ValueError): music.compile_style(SETTINGS|{field:value})
        with self.assertRaises(ValueError): music.compile_style(SETTINGS|{'advanced_prompt':'a'*2000})

    def test_advice_validates_and_never_mutates(self):
        bodies=[]
        def transport(body): bodies.append(body);return reply([item(),item(field='key',original='A minor',suggested='C major')])
        advisor=GeminiAdvisor('secret',transport=transport)
        before=deepcopy(SETTINGS)
        result=music.advise(advisor,SETTINGS,'test')
        self.assertEqual(len(result['suggestions']),2)
        self.assertEqual(before,SETTINGS)
        self.assertNotIn('secret',json.dumps([bodies,result]))
        self.assertNotIn('lyrics',json.loads(bodies[0]['contents'][0]['parts'][0]['text']))
        self.assertFalse(advisor.lock.locked())
        for items in [[item(original='wrong')],[item(suggested='999')],[item(field='advanced_prompt')],[item(reason='')],[item(),item()]]:
            advisor.transport=lambda body:reply(items)
            with self.assertRaises(AdvisorError): music.advise(advisor,SETTINGS)
            self.assertFalse(advisor.lock.locked())
        advisor.transport=lambda body:reply([], 'MAX_TOKENS')
        with self.assertRaises(AdvisorError):music.advise(advisor,SETTINGS)

    def test_no_key_and_shared_busy_lock(self):
        with self.assertRaises(AdvisorError) as caught:music.advise(GeminiAdvisor(),SETTINGS)
        self.assertEqual(caught.exception.status,503)
        advisor=GeminiAdvisor('key');advisor.lock.acquire()
        try:
            with self.assertRaises(AdvisorError) as caught:music.advise(advisor,SETTINGS)
            self.assertEqual(caught.exception.status,409)
        finally:advisor.lock.release()

class MusicApiTests(unittest.TestCase):
    setUp=test_web.WebTests.setUp
    tearDown=test_web.WebTests.tearDown
    request=test_web.WebTests.request

    def test_guide_preview_advice_security(self):
        self.assertEqual(len(json.loads(self.request('GET','/api/music/guide')[2])['fields']),6)
        data={'music_settings':SETTINGS}
        code,_,body=self.request('POST','/api/music/preview',data)
        self.assertEqual(code,200);self.assertEqual(json.loads(body)['style'],music.compile_style(SETTINGS))
        self.assertEqual(self.request('POST','/api/music/preview',{'music_settings':{'bpm':0}})[0],400)
        self.assertEqual(self.request('POST','/api/music/advice',data,{'Origin':'https://foreign.test'})[0],403)
        self.assertEqual(self.request('POST','/api/music/advice',data)[0],503)
        self.studio.advisor=GeminiAdvisor('test',transport=lambda body:reply([item()]))
        self.assertEqual(self.request('POST','/api/music/advice',data)[0],200)

    def test_raw_settings_generation(self):
        payload=dict(self.data);payload.pop('style');payload['music_settings']=SETTINGS
        self.assertEqual(self.request('POST','/api/jobs',payload|{'style':'ambiguous'})[0],400)
        self.assertEqual(self.request('POST','/api/jobs',payload)[0],202)
        self.release.set()
        for _ in range(100):
            if self.received:break
            test_web.time.sleep(.01)
        generated=self.received[0][1]
        self.assertEqual(generated['music_settings'],SETTINGS)
        self.assertEqual(generated['style'],music.compile_style(SETTINGS))
        cli.validate_input(generated)
        with self.assertRaises(ValueError):cli.validate_input(generated|{'style':'wrong'})

    def test_structured_snapshot_replay(self):
        data=dict(self.data)|metadata.generation_input(SONG)
        cli.save_json(self.folder/'metadata.json',dict(schema_version=2,id='123456-abcdef12',input=data,config=self.config,status='succeeded',created_at='2026-09-23'))
        state=json.loads(self.request('GET','/api/state')[2])
        self.assertEqual(state['tracks'][0]['input']['song']['music_settings'],SETTINGS)
        self.assertEqual(self.request('POST','/api/replay',{'id':self.run_id})[0],202)
        self.release.set()
        for _ in range(100):
            if self.received:break
            test_web.time.sleep(.01)
        self.assertEqual(self.received[0][1],data)
