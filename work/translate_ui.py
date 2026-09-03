import concurrent.futures
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "source"
OUT = ROOT / "work" / "translated"
# Token safety used for resumable checkpoints. URLs end before Minecraft's literal %n.
FORMAT = re.compile(r"%(?:n|%|(?:\d+\$)?[-#+ 0,(<]*\d*(?:\.\d+)?[bBhHsScCdoxXeEfgGaAtT])")
COLOR = re.compile(r"§.")
URL = re.compile(r"https?://.*?(?=%n|\s|§|$)")

def tokens(value):
 return FORMAT.findall(value), COLOR.findall(value), URL.findall(value)

JOBS = {
 "betterquesting-gui": ("betterquesting-gui.lang", "translate every value as concise Vietnamese game UI"),
 "bqtweaker": ("bqtweaker.lang", "translate every value as concise Vietnamese game UI"),
 "crafttweaker": ("crafttweaker.lang", "for keys ending .name copy English unchanged; translate other tooltip/message values; preserve item names English"),
 "enchantment_descriptions": ("enchantment_descriptions.lang", "translate descriptions; preserve enchantment/item/mod names English"),
 "divine_journey_2": ("divine_journey_2.lang", "for keys ending .name copy English unchanged; translate other tooltip/JEI prose; preserve item/mod names English"),
}

PROMPT='''Translate Minecraft Divine Journey 2 localization entries from English to natural Vietnamese. Return ONLY a valid JSON object mapping every exact input key to output string. {rule}. Keep all item/block/mob/mod/dimension/multiblock/proper names English for JEI/wiki. Preserve every %n, %%, Java format token, § code and URL exactly. Never create a bare percent. Concise, friendly, human game voice. INPUT JSON:\n'''

def parse_lang(p):
 d={}
 for line in p.read_text(encoding='utf-8-sig').splitlines():
  if '=' in line and not line.lstrip().startswith('#'):
   k,v=line.split('=',1);d[k]=v
 return d

def valid(src,tgt):
 return set(src)==set(tgt) and all(tokens(src[k])==tokens(tgt[k]) for k in src)

def run(name):
 source_name,rule=JOBS[name]; src=parse_lang(SRC/source_name); outp=OUT/(name+'.json')
 if outp.exists():
  try:
   if valid(src,json.loads(outp.read_text(encoding='utf-8'))):return name,'already-valid'
  except:pass
 result={}
 if outp.exists():
  try:
   partial=json.loads(outp.read_text(encoding='utf-8'))
   # Resume only a valid prefix so a transient provider failure does not discard work.
   if list(partial)==list(src)[:len(partial)] and all(tokens(src[k])==tokens(v) for k,v in partial.items()):
    result.update(partial)
  except Exception:
   pass
 items=list(src.items()); chunk=12
 for i in range(len(result),len(items),chunk):
  batch=dict(items[i:i+chunk]); prompt=PROMPT.format(rule=rule)+json.dumps(batch,ensure_ascii=False)
  ok=False
  for attempt in range(3):
   cp=subprocess.run(['hermes','-z',prompt,'--cli','--ignore-user-config','--ignore-rules','--safe-mode','-t',''],capture_output=True,text=True,encoding='utf-8',timeout=600)
   if cp.returncode:continue
   text=cp.stdout.strip()
   try:got=json.loads(text)
   except:
    try:got=json.loads(text[text.find('{'):text.rfind('}')+1])
    except:continue
   if set(got)==set(batch) and all(tokens(batch[k])==tokens(got[k]) for k in batch):ok=True;break
  if not ok:
   # Fall back to preserving the exact English chunk. This is safer than emitting
   # broken formatting and still keeps item/JEI terminology searchable.
   got=batch
   print(name,'fallback-english',i,flush=True)
  result.update(got); OUT.mkdir(parents=True,exist_ok=True);outp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  print(name,len(result),'/',len(src),flush=True)
 if not valid(src,result):raise RuntimeError(name+' final validation')
 return name,'translated'

def main():
 with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
  for f in concurrent.futures.as_completed([ex.submit(run,n) for n in JOBS]):print(f.result(),flush=True)
if __name__=='__main__':main()
