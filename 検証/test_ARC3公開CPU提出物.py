from __future__ import annotations
import ast, base64, hashlib, importlib.util, json, os, re, shutil, sys, tempfile, types, unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO = Path(os.environ['ARC3_TEST_REPO']) if 'ARC3_TEST_REPO' in os.environ else HERE.parent
REFERENCE = Path(os.environ['ARC3_REFERENCE_NOTEBOOK']) if 'ARC3_REFERENCE_NOTEBOOK' in os.environ else None
BUILDER_PATH = HERE/'cpu_builder.py' if (HERE/'cpu_builder.py').is_file() else REPO/'道具/ARC3公開CPU提出物/cpu_builder.py'
spec = importlib.util.spec_from_file_location('cpu_builder', BUILDER_PATH)
builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)

class BuilderTests(unittest.TestCase):
 def setUp(self):
  self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
  self.root = Path(self.tmp.name); self.out = self.root/'out'
  self.result = builder.build(REPO,self.out,owner='owner',slug='candidate',title='candidate')
  self.nb = json.loads((self.out/'cpu-prototype.ipynb').read_text('utf8'))
  self.sources = [c['source'] for c in self.nb['cells'] if c['cell_type']=='code']
 def test_exact_submitted_cells(self):
  if REFERENCE is None: self.skipTest('exact version 2 Notebook not supplied')
  self.assertTrue(REFERENCE.is_file(), 'explicit reference Notebook path is invalid')
  ref=json.loads(REFERENCE.read_text('utf8'))
  norm=lambda c: ''.join(c['source']) if isinstance(c['source'],list) else c['source']
  self.assertEqual([norm(c) for c in ref['cells']],[norm(c) for c in self.nb['cells']])
 def test_pinned_source_bytes_and_notebook_hash(self):
  self.assertEqual(self.result['notebook_sha256'],'59091c6b4afb8b8c4601d6267a8b6fe1b2f08facd24daeafd35847354dc083a4')
  node=next(x for x in ast.parse(self.sources[1]).body if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='entries' for t in x.targets)); entries=ast.literal_eval(node.value)
  self.assertEqual(set(entries),{'my_agent.py','main.py','swarm.py','STARTER-MIT-LICENSE.txt'})
  for entry in entries.values(): self.assertEqual(hashlib.sha256(base64.b64decode(entry['bytes'],validate=True)).hexdigest(),entry['sha256'])
  self.assertEqual(base64.b64decode(entries['my_agent.py']['bytes']),(REPO/'接続/ARC3公開探索agent.py').read_bytes())
  self.assertEqual(base64.b64decode(entries['STARTER-MIT-LICENSE.txt']['bytes']),(REPO/'STARTER-MIT-LICENSE.txt').read_bytes())
 def test_private_offline_metadata_and_dependency(self):
  m=json.loads((self.out/'kernel-metadata.json').read_text('utf8'))
  self.assertTrue(m['is_private']); self.assertFalse(m['enable_gpu']); self.assertFalse(m['enable_tpu']); self.assertFalse(m['enable_internet']); self.assertEqual(m['competition_sources'],[builder.COMPETITION])
  self.assertIn("'--no-index'",self.sources[0]); self.assertIn('arc_agi_3_wheels',self.sources[0]); self.assertIn('arc-agi==0.9.8',self.sources[0]); self.assertIn('arcengine==0.9.3',self.sources[0])
 def test_refuse_overwrite(self):
  marker=self.out/'keep'; marker.write_text('unchanged')
  with self.assertRaises(FileExistsError): builder.build(REPO,self.out,owner='owner',slug='candidate',title='candidate')
  self.assertEqual(marker.read_text(),'unchanged')
 def test_wrong_agent_rejected_before_output(self):
  fake=self.root/'fake'; (fake/'接続').mkdir(parents=True); (fake/'接続/ARC3公開探索agent.py').write_text('bad'); shutil.copyfile(REPO/'STARTER-MIT-LICENSE.txt',fake/'STARTER-MIT-LICENSE.txt')
  rejected=self.root/'rejected'
  with self.assertRaises(ValueError): builder.build(fake,rejected,owner='owner',slug='candidate',title='candidate')
  self.assertFalse(rejected.exists())
 def test_modified_starter_rejected(self):
  fake=self.root/'stage'; (fake/'starter').mkdir(parents=True); (fake/'starter/main.py').write_text('bad'); shutil.copyfile(builder.HERE/'starter/swarm.py',fake/'starter/swarm.py'); rejected=self.root/'rejected'
  with mock.patch.object(builder,'HERE',fake),self.assertRaises(ValueError): builder.build(REPO,rejected,owner='owner',slug='candidate',title='candidate')
  self.assertFalse(rejected.exists())
 def test_unknown_flag_rejected_and_normal_placeholder_only(self):
  run=self.sources[2]
  with mock.patch.dict(os.environ,{'KAGGLE_IS_COMPETITION_RERUN':'unknown'}):
   with self.assertRaises(RuntimeError): exec(run,{})
  fake=types.ModuleType('pandas'); fake.DataFrame=lambda *args,**kwargs: types.SimpleNamespace(to_parquet=lambda path,index: self.assertTrue(path.endswith('/submission.parquet')))
  with mock.patch.dict(os.environ,{'KAGGLE_IS_COMPETITION_RERUN':'false'}),mock.patch.dict(sys.modules,{'pandas':fake}),mock.patch('socket.create_connection',side_effect=AssertionError('unexpected gateway')),mock.patch('subprocess.run',side_effect=AssertionError('unexpected runner')): exec(run,{})
 def test_rerun_starts_runner_without_placeholder(self):
  run=self.sources[2]; source=self.root/'starter_input'; (source/'agents/templates').mkdir(parents=True); (source/'agents/__init__.py').write_text(''); bundle=self.root/'bundle'; bundle.mkdir()
  for name in ('my_agent.py','main.py','swarm.py'): (bundle/name).write_text('# fixture')
  working=self.root/'work'; output=self.root/'submission.parquet'
  for old,new in [('/kaggle/input/competitions/arc-prize-2026-arc-agi-3/ARC-AGI-3-Agents',source.as_posix()),('/tmp/arc3-cpu-starter',working.as_posix()),('/tmp/arc3-cpu-agent',bundle.as_posix()),('/kaggle/working/submission.parquet',output.as_posix())]: run=run.replace(old,new)
  conn=mock.MagicMock(); calls=[]
  with mock.patch.dict(os.environ,{'KAGGLE_IS_COMPETITION_RERUN':'true'}),mock.patch('socket.create_connection',return_value=conn),mock.patch('subprocess.run',side_effect=lambda cmd,**kw: calls.append(cmd)),mock.patch.dict(sys.modules,{'pandas':None}): exec(run,{})
  self.assertEqual(len(calls),1); self.assertEqual(calls[0][-3:],['main.py','--agent','myagent']); self.assertFalse(output.exists()); self.assertNotIn('curl',run)
 def test_no_common_secrets_or_private_imports(self):
  node=next(x for x in ast.parse(self.sources[1]).body if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='entries' for t in x.targets)); entries=ast.literal_eval(node.value)
  for ent in entries.values():
   raw=base64.b64decode(ent['bytes']); self.assertIsNone(re.search(rb'KGAT_[A-Za-z0-9]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',raw)); self.assertNotIn('hds学習系統'.encode('utf8'),raw); self.assertNotIn('ARC3事前記憶'.encode('utf8'),raw)
  self.assertNotIn('C:\\Users\\', BUILDER_PATH.read_text('utf8'))

if __name__=='__main__': unittest.main()
