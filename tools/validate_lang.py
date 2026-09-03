"""Validate Minecraft 1.12.2 .lang translations safely."""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

COLOR = re.compile(r"§.")
AMP = re.compile(r"&[0-9a-fk-orA-FK-OR]")
# Ranges the MC 1.12.2 font can draw but a Vietnamese translation never wants:
# a stray CJK glyph is machine-translation debris ("làm môi介质 cho"), and
# anything above the BMP has no glyph at all and renders as a white box.
CJK_RANGES = ((0x3040, 0x30FF), (0x3400, 0x9FFF), (0xAC00, 0xD7AF))
LOOKS_LIKE_KEY = re.compile(r"[a-z0-9_]+(\.[a-zA-Z0-9_]+){2,}")
VN_DIACRITIC = re.compile(
    r"[ăâđêôơưĂÂĐÊÔƠƯáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]",
    re.I,
)
# A `.name` under one of these prefixes is the display name JEI and the wiki
# index on; translating it breaks item search. The prefix alone is not enough,
# because `.name` is also the suffix for GUI labels, booklet entries, aspects
# and perks -- 624 of the 919 `.name` keys that ship are deliberately Vietnamese.
# Only the registry namespaces below are off-limits.
REG_NAME_PREFIXES = (
    "item.", "tile.", "block.", "fluid.", "entity.", "material.",
    "potion.", "enchantment.", "itemGroup.", "biome.", "death.",
)
# Require a conversion character immediately after optional flags/width.
# A space is not a valid flag here: otherwise ordinary prose such as "% to"
# gets misclassified as a `%t` placeholder and makes valid translations fail.
FORMAT = re.compile(r"%(?:n|%|(?:\d+\$)?[-#+0,(<]*\d*(?:\.\d+)?[bBhHsScCdoxXeEfgGaAtT])")
ANY_PERCENT = re.compile(r"%")
# Minecraft .lang values encode line breaks as literal %n; URLs stop before them.
URL = re.compile(r"https?://.*?(?=%n|\s|§|$)")


@dataclass(frozen=True)
class Err:
    code: str
    key: str
    detail: str


def parse_lang_text(text: str):
    entries = OrderedDict()
    duplicates = []
    for lineno, raw in enumerate(text.lstrip("\ufeff").splitlines(), 1):
        line = raw.rstrip("\r\n")
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in entries:
            duplicates.append((key, lineno))
        entries[key] = value
    return entries, duplicates


def load_lang(path):
    return parse_lang_text(Path(path).read_text(encoding="utf-8-sig"))


def _format_tokens(value: str):
    tokens = FORMAT.findall(value)
    consumed = "".join(tokens)
    # Bare '%' count is total percent chars minus those represented by valid tokens.
    bare = value.count("%") - consumed.count("%")
    return tokens, bare


def validate(src, tgt, protected, source_duplicates=(), target_duplicates=()):
    errors = []
    for key, lineno in source_duplicates:
        errors.append(Err("SOURCE_DUPLICATE_KEY", key, f"dòng {lineno}"))
    for key, lineno in target_duplicates:
        errors.append(Err("DUPLICATE_KEY", key, f"dòng {lineno}"))
    for key in src:
        if key not in tgt:
            errors.append(Err("MISSING_KEY", key, "thiếu key trong bản dịch"))
    for key in tgt:
        if key not in src:
            errors.append(Err("EXTRA_KEY", key, "key không có trong bản gốc"))
    for key in src.keys() & tgt.keys():
        s, t = src[key], tgt[key]
        st, sbare = _format_tokens(s)
        tt, tbare = _format_tokens(t)
        if st != tt or sbare != tbare:
            errors.append(Err("FORMAT_TOKENS", key, f"gốc {st}/bare={sbare}; dịch {tt}/bare={tbare}"))
        if s.count("%n") != t.count("%n"):
            errors.append(Err("PCT_N_COUNT", key, f"%n: gốc {s.count('%n')} vs dịch {t.count('%n')}"))
        if COLOR.findall(s) != COLOR.findall(t):
            errors.append(Err("COLOR_CODES", key, f"mã màu đổi: {COLOR.findall(s)} -> {COLOR.findall(t)}"))
        for url in URL.findall(s):
            if url not in t:
                errors.append(Err("URL_LOST", key, f"mất link: {url}"))
        for term in protected:
            if term in s and term not in t:
                errors.append(Err("PROTECTED_TERM", key, f"tên riêng/item bị đổi: {term!r}"))
        # MC nối các chuỗi này lại, nên dấu cách viền là nội dung chứ không
        # phải định dạng: "Máu: " + 20 mà mất dấu cách sẽ ra "Máu:20", và hai
        # dấu cách đầu dòng là thụt lề mục con nên phải đếm chứ không hỏi
        # có/không. Bỏ qua văn xuôi dài (>120) vì sách tự xuống dòng và
        # upstream hay để thừa một dấu cách cuối đoạn.
        lead_s = len(s) - len(s.lstrip(" "))
        lead_t = len(t) - len(t.lstrip(" "))
        if lead_s != lead_t:
            errors.append(Err("LEADING_SPACE", key, f"dấu cách đầu: gốc {lead_s} vs dịch {lead_t}"))
        tail_s = len(s) - len(s.rstrip(" "))
        tail_t = len(t) - len(t.rstrip(" "))
        if tail_s != tail_t and (len(s) <= 120 or tail_s == 0):
            errors.append(Err("TRAILING_SPACE", key, f"dấu cách cuối: gốc {tail_s} vs dịch {tail_t}"))
        # A real tab survives the .lang parse (unlike a newline, which truncates
        # the record) but MC 1.12's bitmap font has no glyph for U+0009, so it
        # renders as a missing-character box. Sources spell it `\t`.
        if "\t" in t:
            errors.append(Err("RAW_TAB", key, "có tab thật, MC 1.12 không vẽ được"))
        if t.count("\\t") != s.count("\\t"):
            errors.append(Err("LITERAL_T_COUNT", key, f"\\t: gốc {s.count(chr(92)+'t')} vs dịch {t.count(chr(92)+'t')}"))
        # Một U+000A thật sẽ KẾT THÚC entry .lang ngay tại đó: phần còn lại của
        # câu biến mất trong game trong khi mọi phép kiểm byte vẫn xanh. MC
        # 1.12.2 ngắt dòng bằng chuỗi hai ký tự \n, không phải newline thật.
        # 12 mục sách Blood Magic đã xuất xưởng kiểu này, mất tới 90% nội dung.
        if "\n" in t or chr(13) in t:
            errors.append(Err("RAW_NEWLINE", key, "có newline thật, sẽ cắt cụt dòng trong game"))
        if s.count("\\n") != t.count("\\n"):
            errors.append(
                Err("LITERAL_N_COUNT", key, f"\\n: gốc {s.count(chr(92)+'n')} vs dịch {t.count(chr(92)+'n')}")
            )
        # Ký tự CJK là rác dịch máy, không bao giờ là chủ ý; ngoài BMP thì
        # font không có glyph nên hiện ra ô vuông trắng.
        for ch in t:
            point = ord(ch)
            if any(lo <= point <= hi for lo, hi in CJK_RANGES):
                errors.append(Err("CJK_CHAR", key, f"ký tự CJK: {ch!r}"))
                break
            if point > 0xFFFF:
                errors.append(Err("NON_BMP_CHAR", key, f"ký tự ngoài BMP: {ch!r}"))
                break
        # Bản dịch rỗng hoặc trỏ vào một tên khóa khác sẽ xóa hẳn nhãn thay vì
        # dịch sai nó. Chỉ báo khi bản gốc KHÔNG như vậy: upstream có sẵn vài
        # khóa hỏng kiểu này và ta không sửa lệch của upstream.
        plain_t = AMP.sub("", COLOR.sub("", t)).strip()
        plain_s = AMP.sub("", COLOR.sub("", s)).strip()
        if not t.strip() and s.strip():
            errors.append(Err("EMPTY_TRANSLATION", key, "bản dịch rỗng nhưng gốc có nội dung"))
        if LOOKS_LIKE_KEY.fullmatch(plain_t) and plain_t != plain_s:
            errors.append(Err("VALUE_IS_KEY", key, f"giá trị là tên khóa: {plain_t!r}"))
        # Tên hiển thị registry là thứ JEI và wiki lập chỉ mục; dịch nó là phá
        # tìm kiếm vật phẩm. Guard này từng nằm ở validate_translated_locales.py
        # nhưng khớp 0/10.039 khóa ở đó: khóa item./tile. trong vùng ấy toàn là
        # .tooltip. 21 khóa registry thật đi qua chính module này.
        if key.endswith(".name") and key.startswith(REG_NAME_PREFIXES):
            if VN_DIACRITIC.search(t):
                errors.append(Err("REGISTRY_NAME_TRANSLATED", key, f"tên registry bị dịch: {s!r} -> {t!r}"))
    return errors


def write_lang(path, entries, header=None):
    lines = []
    if header:
        lines.extend(f"# {line}" for line in header.splitlines())
    lines.extend(f"{key}={value}" for key, value in entries.items())
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("source")
    p.add_argument("target")
    p.add_argument("--protected")
    args = p.parse_args(argv)
    src, sd = load_lang(args.source)
    tgt, td = load_lang(args.target)
    protected = set(json.loads(Path(args.protected).read_text(encoding="utf-8"))) if args.protected else set()
    errors = validate(src, tgt, protected, sd, td)
    for e in errors:
        print(f"{e.code}\t{e.key}\t{e.detail}")
    print(f"source={len(src)} target={len(tgt)} errors={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
