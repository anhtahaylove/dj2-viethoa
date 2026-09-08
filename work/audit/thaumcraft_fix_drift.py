"""Doi chieu store thaumcraft hien tai voi ban ThaumcraftFix nap sau.

Sau commit 94f470d store da lay JAR nap sau, nen so lech con lai (neu co) la
loi. Script nay cung phan loai ban DICH: khoa nao dich tu van ban CU (BETA26)
thi noi dung tieng Viet co the mo ta sai co che game.
"""
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import instance_paths  # noqa: E402
from extract_runtime_sources import LANG_PATH, parse_lang, is_ui_key  # noqa: E402

STORE = ROOT / 'work/runtime_locale_sources/thaumcraft.lang'
TRANS = ROOT / 'work/translated/runtime_locales/thaumcraft.json'
COLOUR = re.compile('\u00a7.')


def jar_lang(jar_name_part):
    """Doc lang thaumcraft tu JAR co ten chua jar_name_part."""
    for jar in sorted(instance_paths.mods_dir().rglob('*.jar')):
        if jar_name_part.lower() not in jar.name.lower():
            continue
        with zipfile.ZipFile(jar) as zf:
            for name in zf.namelist():
                m = LANG_PATH.match(name)
                if m and m.group(1).lower() == 'thaumcraft':
                    d = parse_lang(zf.read(name).decode('utf-8', 'replace'))
                    return {k: v for k, v in d.items() if is_ui_key(k) and v.strip()}
    return {}


base = jar_lang('Thaumcraft-1.12.2')
fix = jar_lang('ThaumcraftFix')
store = {}
for line in STORE.read_text(encoding='utf-8').split('\n'):
    line = line.rstrip('\r')
    if line.strip() and not line.lstrip().startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        store[k.strip()] = v  # gia tri giu nguyen dau cach cuoi, game can no

# Chan 1: store phai khop ban nap sau (fix thang base).
runtime = dict(base)
runtime.update(fix)
lech = [k for k in store if k in runtime and store[k] != runtime[k]]
print('khoa store:', len(store))
print('khoa lech so voi ban game thuc nap:', len(lech))
for k in lech[:10]:
    print('  ', k)

# Chan 2: trong 172 khoa fix ghi de, khoa nao NOI DUNG khac han base?
overridden = [k for k in fix if k in base and fix[k] != base[k]]
strip = lambda s: COLOUR.sub('', s).strip()
chu_khac = [k for k in overridden if strip(base[k]) != strip(fix[k])]
print()
print('fix ghi de          :', len(overridden))
print('trong do khac CHU   :', len(chu_khac))

# Chan 3: ban dich co dang mo ta co che cu khong?
tr = json.loads(TRANS.read_text(encoding='utf-8'))
co_dich = [k for k in chu_khac if k in tr]
print('trong so do da dich :', len(co_dich))

out = ROOT / 'work/audit/thaumcraft_fix_drift.json'
out.write_text(json.dumps(
    [{'key': k, 'base': base[k], 'fix': fix[k], 'vi': tr.get(k, '')}
     for k in chu_khac],
    ensure_ascii=False, indent=2), encoding='utf-8')
print('da ghi', out.relative_to(ROOT).as_posix())
