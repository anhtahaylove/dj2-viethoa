"""165 khoa ThaumcraftFix viet lai: ban dich hien tai co con dung khong?

Store da khop JAR, nhung ban dich duoc lam tu van ban BETA26 cu. Neu FIX doi
NGHIA cau chu khong chi sua chinh ta, ban dich se lech nghia ma khong gate nao
bat duoc. Phan loai muc do doi de biet khoa nao can doc lai.
"""
import json
import re
import sys
import zipfile
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import instance_paths
from extract_runtime_sources import LANG_PATH, parse_lang


def jar_lang(part):
    for jar in sorted(instance_paths.mods_dir().rglob('*.jar')):
        if part.lower() not in jar.name.lower():
            continue
        with zipfile.ZipFile(jar) as zf:
            for name in zf.namelist():
                m = LANG_PATH.match(name)
                if m and m.group(1).lower() == 'thaumcraft':
                    return parse_lang(zf.read(name).decode('utf-8', 'replace'))
    return {}


base = jar_lang('Thaumcraft-1.12.2')
fix = jar_lang('ThaumcraftFix')
tr = json.loads((ROOT / 'work/translated/runtime_locales/thaumcraft.json')
                .read_bytes().decode('utf-8'))

WORD = re.compile(r"[A-Za-z']+")
muc = Counter()
can_doc = []

for k, fv in fix.items():
    if k not in base or base[k] == fv or k not in tr:
        continue
    bw, fw = WORD.findall(base[k].lower()), WORD.findall(fv.lower())
    ratio = SequenceMatcher(None, bw, fw).ratio()
    them = set(fw) - set(bw)
    bot = set(bw) - set(fw)
    if ratio >= 0.98 and not them and not bot:
        muc['chi doi dinh dang/dau cau'] += 1
    elif ratio >= 0.9:
        muc['sua chu nho'] += 1
    elif ratio >= 0.6:
        muc['viet lai mot phan'] += 1
        can_doc.append((k, ratio, base[k], fv))
    else:
        muc['viet lai han'] += 1
        can_doc.append((k, ratio, base[k], fv))

print('165 khoa doi chu, muc do doi:')
for m, n in muc.most_common():
    print(f'  {n:4}  {m}')
print()
print(f'can doc lai ban dich: {len(can_doc)}')
for k, r, bv, fv in sorted(can_doc, key=lambda x: x[1])[:8]:
    print(f'  [{r:.2f}] {k}')
    print(f'     BETA26: {bv[:95]}')
    print(f'     FIX   : {fv[:95]}')

out = ROOT / 'work/audit/thaumcraft_fix_reword.json'
out.write_text(json.dumps(
    {'muc_do': dict(muc),
     'can_doc_lai': [{'khoa': k, 'giong': round(r, 3), 'beta26': bv, 'fix': fv}
                     for k, r, bv, fv in sorted(can_doc, key=lambda x: x[1])]},
    ensure_ascii=False, indent=2), encoding='utf-8')
print(f'\nda ghi {out.relative_to(ROOT)}')
