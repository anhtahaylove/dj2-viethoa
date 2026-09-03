import argparse
import json
import subprocess
from pathlib import Path

PROMPT = r'''Translate the following Divine Journey 2 Minecraft quest entries from English to natural Vietnamese.
Return ONLY a valid JSON object mapping each exact input key to its Vietnamese translation, with no markdown or commentary.
Rules:
- Include every input key exactly once; preserve key spelling.
- Preserve formatting/control tokens exactly: %n, %s, %1$s, %2$s, formatting codes, numbers, punctuation structure where appropriate.
- Preserve official mod/item/block/entity/mechanic names in English unless a clearly natural Vietnamese rendering is contextual prose; do not invent names.
- Translate titles creatively but accurately, keeping puns where practical.
- Use consistent Minecraft terminology: craft=chế tạo, Right Click=nhấp chuột phải, Sneak=lén/giữ Shift, Mana=Năng lượng Mana.
- Do not add explanations.

INPUT JSON:
'''

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('source')
    ap.add_argument('output')
    ap.add_argument('--chunk',type=int,default=12)
    args=ap.parse_args()
    data=json.loads(Path(args.source).read_text(encoding='utf-8'))
    entries=data['entries']
    out={}
    for i in range(0,len(entries),args.chunk):
        batch={x['key']:x['en'] for x in entries[i:i+args.chunk]}
        cmd=['hermes','-z',PROMPT+json.dumps(batch,ensure_ascii=False),'--cli','--ignore-user-config','--ignore-rules','--safe-mode','-t','']
        cp=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',timeout=600)
        if cp.returncode:
            raise RuntimeError(f'chunk {i}: {cp.stderr}\n{cp.stdout}')
        text=cp.stdout.strip()
        try:
            got=json.loads(text)
        except Exception:
            a=text.find('{'); b=text.rfind('}')
            got=json.loads(text[a:b+1])
        if set(got)!=set(batch):
            raise ValueError(f'chunk {i}: keys mismatch missing={set(batch)-set(got)} extra={set(got)-set(batch)}')
        out.update(got)
        dest=Path(args.output); dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(f'{dest.name}: {len(out)}/{len(entries)}',flush=True)

if __name__=='__main__': main()
