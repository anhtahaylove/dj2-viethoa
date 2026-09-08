"""Trie cau dai (>=4 tu) con nguyen tieng Anh trong pack da dung.

Audit lang_vs_jars dem duoc con so tong, nhung con so do mot minh khong noi
duoc cai nao DANG dich. Quy uoc cua pack la giu nguyen tieng Anh cho ten vat
pham, nghi le, phu phep va chom sao de tra cuu Wiki/JEI, nen phan lon cac dong
"con tieng Anh" la co y. Script nay tach chung ra khoi van xuoi that su.
"""
import json
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))

PACK = ROOT / 'build/DJ2_Viet_Hoa_2.23.4.zip'
OUT = Path(__file__).resolve().parent / 'long_english_lines.json'

COLOUR = re.compile('\u00a7.')
VIET = re.compile(
    r'[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ'
    r'ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ]'
)

# Mot dong la TEN RIENG (giu tieng Anh co y) khi khoa nam trong cac ho nay.
# Danh sach nay duoc rut ra tu chinh corpus: moi tien to o day da duoc doc mau
# va xac nhan chi chua ten vat pham / nghi le / phu phep / chom sao.
NAME_KEYS = (
    'tile.', 'item.', 'entity.', 'block.', 'fluid.', 'enchantment.',
    'potion.', 'lingering_potion.', 'splash_potion.', 'tipped_arrow.',
    'curse.', 'ritual.', 'rite.', 'spell.', 'advancements.',
    'ac.ritual.', 'ac.spell.', 'astralsorcery.constellation.',
    'bloodmagic.ritual.', 'thaumcraft.research.', 'tooltip.',
    'necronomicon.information.',
)
# Hoac khi noi dung khong phai cau: khong dau cau ket, khong tu noi.
SENTENCE_HINT = re.compile(
    r'\b(the|a|an|is|are|to|of|and|or|you|your|it|this|that|with|for|when|'
    r'will|can|be|not|from|as|by|in|on)\b', re.I
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


def is_prose(key, text):
    """True khi dong nay la van xuoi doc duoc, dang cho dich."""
    if key.startswith(NAME_KEYS):
        return False
    # Cu phap lenh, rune, ma ky thuat -- khong phai cau cho nguoi doc.
    if text.startswith(('/', '<', '{', '[')) or '%' in text:
        return False
    return bool(SENTENCE_HINT.search(text)) and len(text.split()) >= 4


def main():
    if not PACK.exists():
        raise SystemExit(f'chua co pack: {PACK} -- chay build_pack.py truoc')

    rows = []
    with zipfile.ZipFile(PACK) as pack:
        for name in sorted(pack.namelist()):
            if not name.endswith('vi_vn.lang'):
                continue
            mod = name.split('/')[1]
            for key, value in load_lang(
                pack.read(name).decode('utf-8', 'replace')
            ).items():
                clean = COLOUR.sub('', value).strip()
                if len(clean.split()) >= 4 and not VIET.search(value):
                    rows.append({
                        'mod': mod, 'key': key, 'text': clean,
                        'prose': is_prose(key, clean),
                    })

    prose = [r for r in rows if r['prose']]
    print(f'cau dai (>=4 tu) con tieng Anh : {len(rows)}')
    print(f'  ten rieng / cu phap (giu)    : {len(rows) - len(prose)}')
    print(f'  van xuoi (can xem xet)       : {len(prose)}')
    print()

    by_mod = defaultdict(int)
    for row in rows:
        by_mod[row['mod']] += 1
    print('=== THEO MOD (top 10) ===')
    for mod, count in sorted(by_mod.items(), key=lambda kv: -kv[1])[:10]:
        print(f'{count:5}  {mod}')

    if prose:
        print()
        print('=== VAN XUOI CAN XEM XET ===')
        for row in prose:
            print(f"  [{row['mod']}] {row['key']}")
            print(f"      {row['text'][:150]}")

    OUT.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print()
    print('da ghi', OUT.relative_to(ROOT).as_posix())


if __name__ == '__main__':
    main()
