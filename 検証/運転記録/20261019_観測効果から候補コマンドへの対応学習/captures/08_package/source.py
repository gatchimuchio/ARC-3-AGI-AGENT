from pathlib import Path
import json,hashlib,resource,tarfile,gzip,shutil,io
resource.setrlimit(resource.RLIMIT_AS,(256*1024**2,256*1024**2))
B=Path("/workspace/scratch/a94ff513b3af/arc-preservation-recovery-20261019/publication_native_inverse"); R=B.parent
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
 return h.hexdigest()
def ref(p):return {'path':str(p),'bytes':p.stat().st_size,'sha256':digest(p)}
def writej(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
m=json.loads((B/'payload_manifest.json').read_text())
assert digest(B/'payload_manifest.json')=='8a44e12135d131127fcd61064479714b913e7b6e2004ea2dc5703cd60f29001f'
assert digest(B/'README.md')=='f083d91b9ed34bcafd1d0b18fd1d14a2a3544b9aa172caef11ef207a3ff3d549'
ad=json.loads((B/'payload_admission.json').read_text())
print('ADMISSION_VERDICT',ad.get('verdict'))
assert ad.get('verdict')=='PASS_PRIVATE_LOSSLESS_PRESERVATION_ONLY'
seal=json.loads((B/'inspection_manifest.json').read_text())
for name,rec in seal['files'].items():
 p=B/name;assert p.stat().st_size==rec['bytes'] and digest(p)==rec['sha256'],name
for name in seal['final_terminal_receipts_outside_self_hash']:
 p=B/name;assert p.is_file()
 if name.endswith('exit.txt'):assert p.read_text().strip()=='0'
print('INSPECTION_SEAL_VERIFIED',len(seal['files']))
entries={}
for r in m['files']:
 p=Path(r['source'])
 assert not p.is_symlink() and p.is_file()
 assert p.stat().st_size==r['bytes'] and digest(p)==r['sha256'],str(p)
 assert r['archive_path'] not in entries
 entries[r['archive_path']]={'source':str(p),'bytes':r['bytes'],'sha256':r['sha256']}
assert len(entries)==230 and sum(x['bytes'] for x in entries.values())==107001988
meta=[B/n for n in ['README.md','payload_manifest.json','payload_admission.json','inspection_manifest.json','resource_ledger.json']]
meta+=sorted(p for p in (B/'inspection_runs').rglob('*') if p.is_file())
meta+=[Path(__file__)]
for p in meta:
 assert not p.is_symlink()
 assert not any(x in str(p.relative_to(B)) for x in ['disclosure','canonical-audit'])
 name='publication/'+p.relative_to(B).as_posix()
 assert name not in entries
 entries[name]={'source':str(p),'bytes':p.stat().st_size,'sha256':digest(p)}
entries=dict(sorted(entries.items()))
am={'schema':'arc3-inverse78-archive-allowlist-v1','status':'PRIVATE_ONLY_PUBLICATION_PAUSED','original_files':230,'original_raw_bytes':107001988,'member_fields':['path','bytes','sha256'],'entries':[[n,r['bytes'],r['sha256']] for n,r in entries.items()]}
(B/'archive_manifest.json').write_text(json.dumps(am,ensure_ascii=False,separators=(',',':'))+'\n')
class Capped:
 def __init__(self,f,cap):self.f=f;self.n=0;self.cap=cap
 def write(self,b):
  if self.n+len(b)>self.cap:raise RuntimeError('Archive cap reached; partial retained, do not retry without allocation')
  v=self.f.write(b);self.n+=v;return v
 def flush(self):return self.f.flush()
 def tell(self):return self.n
out=B/'arc-native-inverse78-checkpoint-20261019.tar.gz'
assert not out.exists()
with out.open('xb') as f:
 with gzip.GzipFile(filename='',mode='wb',compresslevel=6,mtime=0,fileobj=Capped(f,3*1024**2-256*1024)) as gz:
  with tarfile.open(fileobj=gz,mode='w|',format=tarfile.PAX_FORMAT) as tf:
   for n,r in entries.items():
    p=Path(r['source']);ti=tarfile.TarInfo(n);ti.size=r['bytes'];ti.mode=0o644;ti.mtime=0;ti.uid=ti.gid=0;ti.uname=ti.gname=''
    with p.open('rb') as inp:tf.addfile(ti,inp)
seen={}
with tarfile.open(out,mode='r|gz') as tf:
 for ti in tf:
  assert ti.isfile() and ti.name in entries and ti.name not in seen
  r=entries[ti.name];assert ti.size==r['bytes']
  h=hashlib.sha256();n=0
  with tf.extractfile(ti) as f:
   for c in iter(lambda:f.read(1024*1024),b''):h.update(c);n+=len(c)
  assert n==r['bytes'] and h.hexdigest()==r['sha256'],ti.name
  seen[ti.name]=n
assert set(seen)==set(entries)
uncompressed=0
with gzip.open(out,'rb') as f:
 for c in iter(lambda:f.read(1024*1024),b''):uncompressed+=len(c)
for r in m['files']:
 p=Path(r['source']);assert p.stat().st_size==r['bytes'] and digest(p)==r['sha256']
h=hashlib.sha1();h.update(('blob '+str(out.stat().st_size)+'\0').encode())
with out.open('rb') as f:
 for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
v={'schema':'arc3-inverse78-archive-verification-v1','status':'PASS_PRIVATE_ONLY','archive':ref(out),'git_blob_sha1':h.hexdigest(),'members':len(seen),'original_files_unchanged':230,'member_bytes_hashes_all_match':True,'gzip_crc_eof_verified':True,'tar_uncompressed_bytes':uncompressed,'all_zero_tails_preserved_losslessly':True,'archive_manifest_sha256':digest(B/'archive_manifest.json'),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'git_writes':0}
writej(B/'archive_verification.json',v)
print(json.dumps(v,ensure_ascii=False,indent=2))
arc=sum(p.stat().st_size for p in R.rglob('*') if p.is_file() and (p.name.endswith('.tar.gz') or p.name.endswith('.tar.xz')))
allb=sum(p.stat().st_size for p in R.rglob('*') if p.is_file())
unit=sum(p.stat().st_size for p in B.rglob('*') if p.is_file())-out.stat().st_size
assert arc+12467596<=84*1024**2
assert allb-arc<16*1024**2 and unit<1024**2
assert shutil.disk_usage(R).free>1024**3
print(json.dumps({'global_archives':arc,'global_metadata':allb-arc,'unit_metadata':unit,'reserved_oldmirror':12467596,'disk_free':shutil.disk_usage(R).free}))
