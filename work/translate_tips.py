"""Resumably translate server-pack custom loading tips."""
from __future__ import annotations
import json,re,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CFG=ROOT/'Divine_Journey_2.23.4_Server_Pack/config/tips.cfg'
CACHE=Path(__file__).resolve().parent/'translated/tips.json'
PROMPT='''Translate every JSON value from English into natural concise Vietnamese Minecraft loading tips. Return ONLY valid JSON with exactly the same keys, no markdown. Preserve Minecraft mod/item/block/dimension/multiblock/proper names in English for JEI/wiki search. Preserve all numbers, key letters, URLs, RF/tick, LP, GP, EMC, AE2, ME, RAM, chapter numbers. No raw line breaks.'''

def objects(text):
 dec=json.JSONDecoder(strict=False)
 for i,ch in enumerate(text):
  if ch!='{':continue
  try:
   obj,_=dec.raw_decode(text[i:])
   if isinstance(obj,dict):yield obj
  except Exception:pass

def load():
 lines=CFG.read_text(encoding='utf8').splitlines();src={};indexes={};inside=False;n=0
 for i,line in enumerate(lines):
  if 'S:customTips <' in line:inside=True;continue
  if inside and line.strip()=='>':inside=False;continue
  if inside and line.strip():n+=1;k=f'tip.{n:03d}';src[k]=line.strip();indexes[k]=i
 return lines,src,indexes

def main():
 lines,src,indexes=load();CACHE.parent.mkdir(parents=True,exist_ok=True)
 try:done=json.loads(CACHE.read_text(encoding='utf8'))
 except:done={}
 done={k:v for k,v in done.items() if k in src and isinstance(v,str)}
 pending={k:v for k,v in src.items() if k not in done}
 for start in range(0,len(pending),10):
  batch=dict(list(pending.items())[start:start+10]);ok=None
  for attempt in range(5):
   p=subprocess.run(['hermes','chat','-q',PROMPT+'\nINPUT:\n'+json.dumps(batch,ensure_ascii=False),'--model','subscriptions-quality'],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=300)
   cand=[x for x in objects(p.stdout) if set(x)==set(batch)]
   if cand and all(isinstance(v,str) and '\n' not in v and '\r' not in v for v in cand[-1].values()):ok=cand[-1];break
  if ok is None:raise RuntimeError(f'batch failed: {list(batch)}')
  done.update(ok);CACHE.write_text(json.dumps(done,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print('coverage',len(done),len(src),flush=True)
 if set(done)!=set(src):raise RuntimeError('incomplete')
 url=re.compile(r'https?://[^\s\]]+')
 for k in src:
  if url.findall(src[k])!=url.findall(done[k]):raise RuntimeError('URL mismatch '+k)
 for k,i in indexes.items():lines[i]=lines[i][:-len(lines[i].lstrip())]+done[k]
 CFG.write_text('\n'.join(lines)+'\n',encoding='utf8');print('written',CFG)
if __name__=='__main__':main()
