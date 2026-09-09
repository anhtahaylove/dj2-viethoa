from pathlib import Path
import hashlib, json, re, shutil, tempfile, urllib.request, zipfile
ROOT=Path(__file__).resolve().parents[2]
PROJ=ROOT/'dj2-viethoa'; BUILD=PROJ/'build'; SERVER=ROOT/'Divine_Journey_2.23.4_Server_Pack'
PACK=BUILD/'DJ2_Viet_Hoa_2.23.4.zip'; BUNDLE=BUILD/'DJ2_Viet_Hoa_2.23.4_Client_Extract_To_Instance.zip'
# The pack sits in three places under the server pack: two resourcepack folders
# the launcher reads, and the server-pack root, which is the copy the HTTP host
# opens and streams to joining players. Publishing only the first two leaves the
# root serving whatever build was current when the host last started, so players
# download a pack older than the one on disk while every gate still reads green.
TARGETS=[SERVER/'resourcepack'/PACK.name,SERVER/'resourcepacks'/PACK.name,SERVER/PACK.name]
def digest(p,kind):
 h=hashlib.new(kind);h.update(p.read_bytes());return h.hexdigest()
def atomic_copy(src,dst):
 # The staging file is written next to the destination so the rename stays on
 # one volume, but that directory is the one the HTTP host serves. Windows
 # refuses the replace while the host has the pack open, and without cleanup a
 # 1.9 MB temp file is left sitting in the served directory.
 dst.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile(dir=str(dst.parent),delete=False) as f:
  f.write(src.read_bytes());tmp=Path(f.name)
 try:
  tmp.replace(dst)
 except PermissionError as exc:
  tmp.unlink(missing_ok=True)
  raise SystemExit(
   f'Cannot replace {dst.name}: it is open elsewhere (the resource-pack host '
   'serves this directory). Stop the host, publish, then start it again.\n'
   f'Original error: {exc}'
  ) from exc
def main():
 if not PACK.exists() or not BUNDLE.exists():raise SystemExit('missing build artifacts')
 with zipfile.ZipFile(PACK) as z:
  if z.testzip() is not None:raise SystemExit('resource pack CRC failure')
 with zipfile.ZipFile(BUNDLE) as z:
  if z.testzip() is not None:raise SystemExit('client bundle CRC failure')
 sha1=digest(PACK,'sha1');sha256=digest(PACK,'sha256')
 for target in TARGETS:atomic_copy(PACK,target)
 props=SERVER/'server.properties';text=props.read_text(encoding='utf-8')
 text,n=re.subn(r'(?m)^resource-pack-sha1=.*$',f'resource-pack-sha1={sha1}',text)
 if n!=1:raise SystemExit('resource-pack-sha1 property missing/duplicate')
 props.write_text(text,encoding='utf-8',newline='\n')
 for target in TARGETS:
  if digest(target,'sha1')!=sha1:raise SystemExit('published resource pack mismatch')
 # Verify the already-configured server URL without printing its authority.
 m=re.search(r'(?m)^resource-pack=(.*)$',text)
 url=m.group(1).strip().replace('\\:',':') if m else ''
 http={}
 if not url:
  # The record's only measured field is this download. Writing the report with
  # http={} would keep server_properties_sha1_matches=True and exit 0, so the
  # file would still read as a successful publish while the proof that anyone
  # can actually fetch the pack had been replaced by nothing. Refuse instead.
  raise SystemExit('server.properties has no resource-pack URL, so the publish cannot be verified')
 with urllib.request.urlopen(url,timeout=30) as response:
  body=response.read();http={'status':response.status,'bytes':len(body),'sha1':hashlib.sha1(body).hexdigest()}
 if http['status']!=200 or http['sha1']!=sha1:raise SystemExit('HTTP resource pack does not match')
 report={'resource_pack':{'path':str(PACK),'bytes':PACK.stat().st_size,'sha1':sha1,'sha256':sha256},'client_bundle':{'path':str(BUNDLE),'bytes':BUNDLE.stat().st_size,'sha1':digest(BUNDLE,'sha1'),'sha256':digest(BUNDLE,'sha256')},'published':[str(x) for x in TARGETS],'http':http,'server_properties_sha1_matches':True}
 (BUILD/'publish_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
