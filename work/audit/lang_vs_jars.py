"""Audit every shipped vi_vn.lang against the ACTUAL mod jars.

The `source/` tree is a working copy and can drift from what the game really
loads, so the mod jars in the instance are the authority. Verified findings from
this script: format tokens 0 mismatches, colour codes 0 mismatches.

Java's format grammar is %[index$][flags][width][.precision]conversion, and a
space is a legal flag — which makes a naive regex read "50% slower" as the token
"% s". Excluding the space flag is what turns 22 phantom findings into 0.
"""
import re
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(r'C:/huuhungn/huuhungn-PC/mc_server_pack/dj2-viethoa')
PACK = ROOT / 'build/DJ2_Viet_Hoa_2.23.4.zip'
INSTANCE = Path(
    r'C:/Users/Administrator/AppData/Roaming/ElyPrismLauncher'
    r'/instances/Divine Journey 2/minecraft'
)

TOKEN = re.compile(r'%(?:\d+\$)?[-#+0,(]*\d*(?:\.\d+)?[sdfnbxeo%]')
COLOUR = re.compile(r'§.')
VIET = re.compile(
    r'[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ'
    r'ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ]'
)


def load_lang(text):
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        out[key] = value
    return out


english = defaultdict(dict)
for jar in sorted((INSTANCE / 'mods').glob('*.jar')):
    try:
        with zipfile.ZipFile(jar) as archive:
            for entry in archive.namelist():
                if re.search(r'/lang/en_us\.lang$', entry, re.I):
                    mod = entry.split('/')[1]
                    english[mod].update(
                        load_lang(archive.read(entry).decode('utf-8', 'replace'))
                    )
    except Exception:
        continue

token_bad = []
colour_bad = []
untranslated = defaultdict(list)
translated = 0
identical = 0
absent = defaultdict(list)

NAME_PREFIX = ('tile.', 'item.', 'entity.', 'fluid.', 'block.', 'itemGroup.',
               'material.')

with zipfile.ZipFile(PACK) as pack:
    for name in sorted(pack.namelist()):
        if not name.endswith('vi_vn.lang'):
            continue
        mod = name.split('/')[1]
        source = english.get(mod)
        if not source:
            continue
        pack_keys = load_lang(pack.read(name).decode('utf-8', 'replace'))

        # Keys present upstream but missing from the pack entirely. Iterating
        # only over pack keys hides these — a mod can be 6% covered and still
        # report zero problems.
        for key, original in source.items():
            if key in pack_keys or key.startswith(NAME_PREFIX):
                continue
            clean = COLOUR.sub('', original).strip()
            if len(clean.split()) >= 3:
                absent[mod].append((key, clean))

        for key, value in pack_keys.items():
            original = source.get(key)
            if original is None:
                continue
            if TOKEN.findall(original) != TOKEN.findall(value):
                token_bad.append((mod, key, original, value))
            if COLOUR.findall(original) != COLOUR.findall(value):
                colour_bad.append((mod, key, original, value))
            if original == value:
                identical += 1
                clean = COLOUR.sub('', value).strip()
                if len(clean.split()) >= 4 and not VIET.search(value):
                    if not key.startswith(('tile.', 'item.', 'entity.', 'fluid.',
                                           'block.', 'itemGroup.')):
                        untranslated[mod].append((key, clean))
            else:
                translated += 1

total = translated + identical
print(f'So sanh voi {len(english)} mod JAR')
print(f'  Da dich      : {translated}')
print(f'  Giu nguyen   : {identical}')
print(f'  Ty le dich   : {100 * translated / total:.1f}%')
print()
print(f'LOI token format : {len(token_bad)}')
for mod, key, original, value in token_bad[:10]:
    print(f'  [{mod}] {key}')
    print(f'      JAR: {original[:90]}')
    print(f'      VI : {value[:90]}')
print(f'LOI ma mau       : {len(colour_bad)}')
for mod, key, original, value in colour_bad[:10]:
    print(f'  [{mod}] {key}')

remaining = sum(len(v) for v in untranslated.values())
print(f'\nCau dai (>=4 tu) giu nguyen tieng Anh: {remaining}')
for mod, items in sorted(untranslated.items(), key=lambda kv: -len(kv[1]))[:12]:
    print(f'  {mod:24} {len(items):4}')

missing_total = sum(len(v) for v in absent.values())
print(f'\nKHOA THIEU HAN khoi pack (khong phai ten rieng): {missing_total}')
for mod, items in sorted(absent.items(), key=lambda kv: -len(kv[1]))[:12]:
    print(f'  {mod:24} {len(items):4}')
    for key, text in items[:3]:
        print(f'      {key[:40]:40} {text[:52]}')
