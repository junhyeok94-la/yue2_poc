import json
import unittest
from pathlib import Path
import test_web
import test_cli
from music_studio import cli, score

ABC='X:1\nM:4/4\nL:1/4\nQ:1/4=90\nK:C\nC D E F | G4 |'

class ScoreTests(unittest.TestCase):
    def test_basic_validation_and_headers(self):
        self.assertEqual(score.inspect(ABC)['headers']['Q'],'1/4=90')
        for bad in [None,'','K:C','C D E F','K:C\nC\0D','a'*24001]:
            with self.assertRaises(ValueError):score.validate_abc(bad)
    def test_generated_and_submitted_artifacts_and_limits(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            self.assertIsNone(score.read(folder))
            (folder/'score.abc').write_text(ABC,encoding='utf8')
            self.assertEqual(score.read(folder)['source'],'generated')
            (folder/'input.abc').write_text(ABC+'\nG4',encoding='utf8')
            self.assertEqual(score.read(folder)['source'],'provided')
            (folder/'input.abc').write_text('a'*24001)
            with self.assertRaises(ValueError):score.read(folder)

class ScoreGenerationTests(unittest.TestCase):
    setUp=test_cli.GenerationTests.setUp
    def test_external_score_file_command_and_snapshot(self):
        data=self.data|{'cot':'melody','abc':ABC}
        def runner(command,log,timeout):
            folder=Path(command[command.index('--out')+1]).parent
            self.assertEqual((folder/'input.abc').read_text(encoding='utf8'),ABC)
            self.assertIn('abc_file='+str(folder/'input.abc'),command)
            self.assertIn('--out-dir',command)
            return test_cli.GenerationTests.valid_runner(command,log,timeout)
        folder,meta=cli.generate(self.config,data,self.root/'outputs',runner=runner)
        self.assertEqual(meta['status'],'succeeded')
        self.assertEqual(meta['input']['abc'],ABC)
        self.assertEqual(meta['score']['source'],'provided')
        original=(folder/'input.abc').read_bytes()
        again,second=cli.generate(self.config,meta['input'],self.root/'outputs',runner=runner,parent_id=meta['id'])
        self.assertEqual((again/'input.abc').read_bytes(),original)
        self.assertEqual(second['parent_id'],meta['id'])
    def test_planner_export_and_off_compatibility(self):
        self.assertNotIn('--out-dir',cli.build_command(self.config,self.data,self.root/'audio.wav'))
        with self.assertRaises(ValueError):cli.validate_input(self.data|{'abc':ABC})
        def runner(command,log,timeout):
            folder=Path(command[command.index('--out-dir')+1]);(folder/'score.abc').write_text(ABC,encoding='utf8')
            return test_cli.GenerationTests.valid_runner(command,log,timeout)
        _,meta=cli.generate(self.config,self.data|{'cot':'full'},self.root/'outputs',runner=runner)
        self.assertEqual(meta['score']['source'],'generated')

class ScoreApiTests(unittest.TestCase):
    setUp=test_web.WebTests.setUp
    tearDown=test_web.WebTests.tearDown
    request=test_web.WebTests.request
    def test_read_download_inspect_and_paths(self):
        self.assertEqual(self.request('GET','/api/score?id='+self.run_id)[0],404)
        (self.folder/'score.abc').write_text(ABC,encoding='utf8')
        code,_,body=self.request('GET','/api/score?id='+self.run_id)
        self.assertEqual(code,200);self.assertEqual(json.loads(body)['abc'],ABC)
        code,headers,body=self.request('GET','/api/score?id='+self.run_id+'&download=1')
        self.assertEqual(body.decode(),ABC);self.assertIn('attachment',headers['Content-Disposition'])
        self.assertEqual(self.request('GET','/api/score?id=../../outside')[0],400)
        self.assertEqual(self.request('POST','/api/score/inspect',{'abc':ABC})[0],200)
        self.assertEqual(self.request('POST','/api/score/inspect',{'abc':ABC},{'Origin':'https://foreign.test'})[0],403)
        self.assertEqual(self.request('POST','/api/score/inspect',{'abc':'K:C'})[0],400)
    def test_score_request_preserved_and_off_rejected(self):
        self.assertEqual(self.request('POST','/api/jobs',self.data|{'abc':ABC})[0],400)
        self.assertEqual(self.request('POST','/api/jobs',self.data|{'abc':ABC,'cot':'full'})[0],202)
        self.release.set()
        for _ in range(100):
            if self.received:break
            test_web.time.sleep(.01)
        self.assertEqual(self.received[0][1]['abc'],ABC)
