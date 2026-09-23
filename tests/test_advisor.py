import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import test_web
from music_studio.settings import gemini_settings
from music_studio.lyrics.gemini import GeminiAdvisor, AdvisorError

SECTION=dict(id='s1',type='verse',label='Verse',bars=8,lyrics=['조용한 밤'])
CONTEXT=dict(title='노래',style='Korean R&B')
def response(items,finish='STOP'):
    return {'candidates':[{'finishReason':finish,'content':{'parts':[{'text':json.dumps({'suggestions':items},ensure_ascii=False)}]}}]}
def suggestion(**values):
    return dict(line_index=0,original='조용한 밤',suggested='고요한 이 밤',reason='장면을 또렷하게 합니다.',type='expression')|values

class AdvisorTests(unittest.TestCase):
    def test_env_quotes_precedence_and_model_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory,'.env').write_text('GEMINI_API_KEY="test-key"\nGEMINI_MODEL=gemini-2.5-flash\n',encoding='utf8')
            with patch.dict('os.environ',{},clear=True):
                self.assertEqual(gemini_settings(directory),('test-key','gemini-2.5-flash'))
            with patch.dict('os.environ',{'GEMINI_API_KEY':'override','GEMINI_MODEL':'../../bad'},clear=True):
                with self.assertRaises(ValueError):gemini_settings(directory)
            with patch.dict('os.environ',{'GEMINI_API_KEY':'override'},clear=True):
                self.assertEqual(gemini_settings(directory)[0],'override')

    def test_exact_review_with_revision_and_no_secret(self):
        bodies=[]
        def transport(body):bodies.append(body);return response([suggestion()])
        advisor=GeminiAdvisor('SECRET',transport=transport)
        result=advisor.request('review',SECTION,CONTEXT)
        self.assertEqual(result['suggestions'][0]['original'],SECTION['lyrics'][0])
        self.assertEqual(len(result['source_revision']),64)
        self.assertNotIn('SECRET',json.dumps([bodies,result,advisor.status()]))
        self.assertEqual(SECTION['lyrics'],['조용한 밤'])

    def test_append_and_empty_suggestions(self):
        advisor=GeminiAdvisor('key',transport=lambda body:response([suggestion(line_index=1,original='',suggested='첫 줄\n둘째 줄',type='idea')]))
        self.assertEqual(len(advisor.request('suggest',SECTION,CONTEXT)['suggestions']),1)
        advisor.transport=lambda body:response([])
        self.assertEqual(advisor.request('review',SECTION,CONTEXT)['suggestions'],[])

    def test_rejects_bad_output_and_truncation(self):
        for item in [suggestion(original='wrong'),suggestion(line_index=True),suggestion(suggested='a\nb'),suggestion(reason=''),suggestion(type='bad')]:
            with self.subTest(item=item):
                advisor=GeminiAdvisor('key',transport=lambda body:response([item]))
                with self.assertRaises(AdvisorError):advisor.request('review',SECTION,CONTEXT)
                self.assertFalse(advisor.lock.locked())
        advisor=GeminiAdvisor('key',transport=lambda body:response([],finish='MAX_TOKENS'))
        with self.assertRaises(AdvisorError):advisor.request('review',SECTION,CONTEXT)

    def test_no_key_input_limits_and_concurrency(self):
        with self.assertRaises(AdvisorError):GeminiAdvisor().request('review',SECTION,CONTEXT)
        advisor=GeminiAdvisor('key',transport=lambda body:response([]))
        with self.assertRaises(AdvisorError):advisor.request('review',SECTION|{'lyrics':['가'*4001]},CONTEXT)
        advisor.lock.acquire()
        try:
            with self.assertRaises(AdvisorError) as caught:advisor.request('review',SECTION,CONTEXT)
            self.assertEqual(caught.exception.status,409)
        finally:advisor.lock.release()

    def test_focused_prompts_schema_and_response_types(self):
        for action, phrase in [('rhyme','sound echoes'),('hook','memorable lyrical hook')]:
            captured=[]
            def transport(body):
                captured.append(body)
                return response([suggestion(type=action)])
            advisor=GeminiAdvisor('key',transport=transport)
            result=advisor.request(action,SECTION,CONTEXT)
            self.assertEqual(result['action'],action)
            self.assertEqual(result['suggestions'][0]['type'],action)
            body=captured[0]
            self.assertIn(phrase,body['systemInstruction']['parts'][0]['text'])
            self.assertEqual(body['generationConfig']['responseJsonSchema']['properties']['suggestions']['items']['properties']['type']['enum'],[action])
            self.assertEqual(json.loads(body['contents'][0]['parts'][0]['text'])['action'],action)

    def test_focus_rejects_other_types_bad_source_and_blank_lyrics(self):
        for action in ('rhyme','hook'):
            for item in [suggestion(),suggestion(type=action,original='not the source'),suggestion(type=action,line_index=1)]:
                advisor=GeminiAdvisor('key',transport=lambda body:response([item]))
                with self.assertRaises(AdvisorError):advisor.request(action,SECTION,CONTEXT)
            with self.assertRaises(AdvisorError) as caught:
                GeminiAdvisor('key').request(action,SECTION|{'lyrics':[]},CONTEXT)
            self.assertEqual(caught.exception.status,400)
            advisor=GeminiAdvisor('key',transport=lambda body:response([]))
            self.assertEqual(advisor.request(action,SECTION,CONTEXT)['suggestions'],[])

    def test_provider_errors_redacted(self):
        for code in [400,401,403,404,429,500]:
            err=urllib.error.HTTPError('https://example.invalid/SECRET',code,'SECRET',{},None)
            with patch('urllib.request.urlopen',side_effect=err):
                with self.assertRaises(AdvisorError) as caught:GeminiAdvisor('SECRET').request('review',SECTION,CONTEXT)
                self.assertNotIn('SECRET',str(caught.exception))
        with patch('urllib.request.urlopen',side_effect=TimeoutError('SECRET')):
            with self.assertRaises(AdvisorError) as caught:GeminiAdvisor('SECRET').request('review',SECTION,CONTEXT)
            self.assertNotIn('SECRET',str(caught.exception))

class AdvisorApiTests(unittest.TestCase):
    setUp=test_web.WebTests.setUp
    tearDown=test_web.WebTests.tearDown
    request=test_web.WebTests.request

    def test_status_no_key_and_existing_state(self):
        code,_,body=self.request('GET','/api/advisor')
        self.assertEqual(code,200)
        self.assertFalse(json.loads(body)['configured'])
        self.assertEqual(self.request('POST','/api/advisor',{'action':'review','section':SECTION,'context':CONTEXT})[0],503)
        self.assertEqual(self.request('GET','/api/state')[0],200)
        self.assertEqual(self.request('GET','/.env')[0],404)

    def test_review_csrf_and_no_generation(self):
        self.studio.advisor=GeminiAdvisor('SECRET',transport=lambda body:response([suggestion()]))
        payload={'action':'review','section':SECTION,'context':CONTEXT}
        self.assertEqual(self.request('POST','/api/advisor',payload,{'Origin':'https://example.org'})[0],403)
        code,_,body=self.request('POST','/api/advisor',payload)
        self.assertEqual(code,200)
        self.assertNotIn(b'SECRET',body)
        self.assertIsNone(self.studio.job)

    def test_focused_actions_api_preserve_original_and_do_not_generate(self):
        for action in ('rhyme','hook'):
            self.studio.advisor=GeminiAdvisor('key',transport=lambda body:response([suggestion(type=action)]))
            payload={'action':action,'section':SECTION,'context':CONTEXT}
            code,_,body=self.request('POST','/api/advisor',payload)
            self.assertEqual(code,200)
            self.assertEqual(json.loads(body)['suggestions'][0]['type'],action)
            self.assertEqual(SECTION['lyrics'],['조용한 밤'])
            self.assertIsNone(self.studio.job)
