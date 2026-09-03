"""Build a deterministic Divine Journey 2 Vietnamese resource pack."""
from __future__ import annotations

import json
import shutil
import zipfile
from collections import OrderedDict, defaultdict
from pathlib import Path

from validate_lang import load_lang, validate, write_lang

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source"
TRANS = ROOT / "work" / "translated"
STAGE = ROOT / "build" / "DJ2_Viet_Hoa_2.23.4"
ZIP_OUT = ROOT / "build" / "DJ2_Viet_Hoa_2.23.4.zip"
PROTECTED = set(json.loads((ROOT / "work" / "protected_terms.json").read_text(encoding="utf-8")))
HEADER = "Divine Journey 2 v2.23.4 — Việt hoá bởi cộng đồng. Giữ nguyên tên item/mod bằng English."

# English locale casing is copied exactly from each source mod. vi_vn is always provided
# as the selectable Vietnamese locale; the English override keeps legacy installations working.
SPECS = [
    {
        "source": "betterquesting-quests.lang",
        "namespace": "betterquesting",
        "english_locale": "en_US",
        "translations": [f"ql_{i:02}.json" for i in range(30)] + ["orphans.json", "betterquesting-gui.json"],
    },
    {"source": "bqtweaker.lang", "namespace": "bqtweaker", "english_locale": "en_us", "translations": ["bqtweaker.json"]},
    {"source": "crafttweaker.lang", "namespace": "crafttweaker", "english_locale": "en_us", "translations": ["crafttweaker.json"]},
    {"source": "divine_journey_2.lang", "namespace": "divine_journey_2", "english_locale": "en_us", "translations": ["divine_journey_2.json"]},
]


def load_spec_source(source_name):
    source, duplicates = load_lang(SOURCE / source_name)
    if source_name == "betterquesting-quests.lang":
        gui, gui_duplicates = load_lang(SOURCE / "betterquesting-gui.lang")
        duplicates.extend(sorted(set(source) & set(gui)))
        duplicates.extend(gui_duplicates)
        source.update(gui)
    return source, duplicates


def load_translation(names):
    merged = OrderedDict()
    for name in names:
        path = TRANS / name
        if not path.exists():
            raise FileNotFoundError(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        if "entries" in data:
            raise ValueError(f"{path} vẫn là batch shape, cần direct key→text map")
        duplicate = merged.keys() & data.keys()
        if duplicate:
            raise ValueError(f"Duplicate keys across {names}: {sorted(duplicate)[:5]}")
        merged.update(data)
    return merged


def merge_namespace_entries(stage, namespace, entries):
    """Merge Vietnamese entries without silently overwriting another family."""
    path = stage / f"assets/{namespace}/lang/vi_vn.lang"
    existing = load_lang(path)[0] if path.exists() else OrderedDict()
    conflicts = [key for key in entries if key in existing and existing[key] != entries[key]]
    if conflicts:
        raise ValueError(f"Conflicting translations in {path}: {conflicts[:5]}")
    existing.update(entries)
    write_lang(path, existing, HEADER)


def write_dual_locale(stage, namespace, english_locale, entries):
    """Write pack-owned English fallback plus Vietnamese selectable locale.

    This is reserved for namespaces whose complete source map is owned by this
    project. Overlay families extracted from mod JARs write only vi_vn so they
    cannot replace a mod's full English catalog with a translated subset.
    """
    write_lang(stage / f"assets/{namespace}/lang/{english_locale}.lang", entries, HEADER)
    merge_namespace_entries(stage, namespace, entries)


def add_enchantment_descriptions(stage, report, all_errors):
    source, source_dupes = load_lang(SOURCE / "enchantment_descriptions_all.lang")
    target = load_translation(["enchantment_descriptions_all.json"])
    meta = json.loads((SOURCE / "enchantment_descriptions_meta.json").read_text(encoding="utf-8"))
    errors = validate(source, target, PROTECTED, source_dupes, ())
    report["enchantment_descriptions_all.lang"] = {"source": len(source), "target": len(target), "errors": len(errors)}
    all_errors.extend(("enchantment_descriptions_all.lang", error) for error in errors)
    grouped = defaultdict(OrderedDict)
    locales = {}
    for key, value in target.items():
        info = meta[key]
        grouped[info["namespace"]][key] = value
        locales.setdefault(info["namespace"], info["english_locale"])
    for namespace, entries in grouped.items():
        merge_namespace_entries(stage, namespace, entries)


def add_lang_family(stage, report, all_errors, source_dir, translated_dir, to_namespace, include_stems=None):
    """Ship one translated .lang family, one file per owning mod namespace.

    Each mod's English locale casing is copied exactly from its own JAR, because
    Linux and macOS clients resolve assets/<ns>/lang/<locale>.lang case-sensitively.
    """
    for source_path in sorted(source_dir.glob("*.lang")):
        if include_stems is not None and source_path.stem not in include_stems:
            continue
        namespace = to_namespace(source_path.stem)
        source, source_dupes = load_lang(source_path)
        translated_path = translated_dir / f"{source_path.stem}.json"
        target = json.loads(translated_path.read_text(encoding="utf-8")) if translated_path.exists() else {}
        target = OrderedDict((key, target[key]) for key in source if key in target)
        # Token/protected-term validation runs over the translated subset. Full key
        # coverage is a separate release gate, asserted by the build tests.
        covered = OrderedDict((key, value) for key, value in source.items() if key in target)
        errors = validate(covered, target, PROTECTED, source_dupes, ())
        report[str(source_path.relative_to(ROOT))] = {
            "source": len(source),
            "target": len(target),
            "errors": len(errors),
        }
        all_errors.extend((source_path.name, error) for error in errors)
        if target:
            merge_namespace_entries(stage, namespace, target)


def apply_runtime_locale_casing(stage):
    """Rename runtime vi_vn locales to the exact casing used by each active JAR.

    Windows resolves vi_vn.lang and vi_VN.lang as the same path. Detect the
    staged file case-insensitively, then use a temporary spelling for a real
    case-only rename without deleting a populated locale.
    """
    meta_dir = ROOT / "work" / "runtime_locale_meta"
    for meta_path in sorted(meta_dir.glob("*.json")):
        namespace = meta_path.stem
        english_locale = json.loads(meta_path.read_text(encoding="utf-8"))["english_locale"]
        locale_name = "vi_VN.lang" if english_locale == "en_US.lang" else "vi_vn.lang"
        lang_dir = stage / "assets" / namespace / "lang"
        if not lang_dir.exists():
            continue
        candidates = [path for path in lang_dir.glob("*.lang") if path.name.casefold() == "vi_vn.lang"]
        if not candidates:
            continue
        source = candidates[0]
        if source.name == locale_name:
            continue
        target = lang_dir / locale_name
        temporary = lang_dir / f".{namespace}.locale-case.tmp"
        if temporary.exists():
            temporary.unlink()
        source.rename(temporary)
        if target.exists():
            target.unlink()
        temporary.rename(target)


def add_json_book_tree(stage, report, tree_root, label):
    """Copy a rendered guide-book resource tree verbatim into the pack."""
    if not tree_root.exists():
        report[label] = {"files": 0, "errors": 0}
        return
    count = 0
    for path in sorted(tree_root.rglob("*")):
        if not path.is_file():
            continue
        destination = stage / path.relative_to(tree_root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        count += 1
    report[label] = {"files": count, "errors": 0}


def add_patchouli_metadata(stage, report, all_errors):
    """Merge book titles/landing text that Patchouli resolves through normal .lang keys."""
    source, source_dupes = load_lang(SOURCE / "patchouli_metadata.lang")
    target = json.loads((TRANS / "patchouli_metadata.json").read_text(encoding="utf-8"))
    namespaces = json.loads((SOURCE / "patchouli_metadata_namespaces.json").read_text(encoding="utf-8"))
    target = OrderedDict((key, target[key]) for key in source if key in target)
    errors = validate(source, target, PROTECTED, source_dupes, ())
    if set(namespaces) != set(source):
        errors.append("patchouli metadata namespace map does not exactly match source keys")
    report["patchouli_metadata"] = {"source": len(source), "target": len(target), "errors": len(errors)}
    all_errors.extend(("patchouli_metadata.lang", error) for error in errors)
    grouped = defaultdict(OrderedDict)
    for key, value in target.items():
        grouped[namespaces[key]][key] = value
    for namespace, entries in grouped.items():
        merge_namespace_entries(stage, namespace, entries)


def add_bitmap_font(stage, report):
    """Rasterise the Vietnamese bitmap font pages into the pack.

    Minecraft 1.12.2 ignores modern TTF font providers, so the typeface is baked
    into legacy unicode page atlases instead. Only the three pages holding
    Vietnamese letters are overridden, glyphs are aligned to the vanilla baseline,
    and ASCII widths are left exactly as Mojang shipped them.
    """
    from build_bitmap_font import build as build_font

    client_jar = Path(
        "C:/Users/Administrator/AppData/Roaming/ElyPrismLauncher/libraries"
        "/com/mojang/minecraft/1.12.2/minecraft-1.12.2-client.jar"
    )
    if not client_jar.exists():
        raise SystemExit(f"vanilla client jar required for font metrics: {client_jar}")
    report["bitmap_font"] = build_font(
        SOURCE / "fonts" / "JetBrainsMono-Bold.ttf", stage, client_jar, size=14
    )


def add_advancement_literals(stage, report):
    """Overlay the two advancement JSON files that contain literal display text."""
    inventory = json.loads((ROOT / "work/audit/advancement_literal_inventory.json").read_text(encoding="utf-8"))
    translated_dir = TRANS / "advancement_literals"
    count = 0
    for item in inventory:
        source = SOURCE / "advancement_literals" / item["source_file"]
        translated = translated_dir / item["source_file"]
        source_data = json.loads(source.read_text(encoding="utf-8"))
        target_data = json.loads(translated.read_text(encoding="utf-8"))
        # Only display text may change; criteria, rewards, icons, frame/style, and parents must be byte-semantically identical.
        source_copy = json.loads(json.dumps(source_data))
        target_copy = json.loads(json.dumps(target_data))
        source_copy["display"].pop("title", None)
        source_copy["display"].pop("description", None)
        target_copy["display"].pop("title", None)
        target_copy["display"].pop("description", None)
        if source_copy != target_copy:
            raise RuntimeError(f"Unsafe advancement JSON change: {item['path']}")
        destination = stage / item["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(target_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        count += 1
    report["advancement_literals"] = {"files": count, "errors": 0}


def build(output=None, stage=None):
    output = Path(output) if output is not None else ZIP_OUT
    stage = Path(stage) if stage is not None else STAGE
    # Drop the previous artifact before doing any work that can fail. Otherwise
    # a validation error or a raised exception leaves the old ZIP on disk, and
    # the next pipeline step hashes, publishes and serves the previous release
    # while reporting the new one.
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    report = {}
    all_errors = []
    for spec in SPECS:
        source, source_dupes = load_spec_source(spec["source"])
        target = load_translation(spec["translations"])
        errors = validate(source, target, PROTECTED, source_dupes, ())
        report[spec["source"]] = {"source": len(source), "target": len(target), "errors": len(errors)}
        all_errors.extend((spec["source"], error) for error in errors)
        write_dual_locale(stage, spec["namespace"], spec["english_locale"], target)
    add_enchantment_descriptions(stage, report, all_errors)
    add_lang_family(
        stage,
        report,
        all_errors,
        SOURCE,
        TRANS,
        lambda stem: stem.removeprefix("p2_"),
        include_stems={
            "requious_frakto",
            "p2_chisel",
            "p2_groovyscript",
            "p2_roots",
            "p2_ftbutilities",
            "p2_ftblib",
            "p2_ftbbackups",
            "p2_jei",
            "p2_jeiutilities",
            "p2_jeresources",
            "p2_enderutilities",
            "p2_actuallyadditions",
            "p2_extrautils2",
        },
    )
    add_patchouli_metadata(stage, report, all_errors)
    add_lang_family(
        stage,
        report,
        all_errors,
        SOURCE / "books",
        TRANS,
        lambda stem: stem.removeprefix("books_"),
        # `books_bloodmagic` is excluded: its 274 guide keys are registered by
        # the JAR under `bloodmagicguide`, never under `bloodmagic`. Emitting
        # them here produced a second, dead copy of every entry that the game
        # never read, and the two copies had already drifted apart (36 keys,
        # including 12 real tab characters MC 1.12 cannot draw). The single
        # surviving copy lives in work/translated/runtime_locales/.
        include_stems={p.stem for p in (SOURCE / "books").glob("*.lang")} - {"books_bloodmagic"},
    )
    add_lang_family(
        stage,
        report,
        all_errors,
        SOURCE / "tooltips",
        TRANS / "tooltips",
        lambda stem: stem,
    )
    add_lang_family(
        stage,
        report,
        all_errors,
        SOURCE / "advancements",
        TRANS / "advancements",
        lambda stem: stem,
    )
    add_lang_family(
        stage,
        report,
        all_errors,
        ROOT / "work" / "runtime_locale_sources",
        TRANS / "runtime_locales",
        lambda stem: stem,
    )
    # Apply source-JAR casing only after every locale family has been merged;
    # otherwise a later family can recreate vi_vn beside vi_VN on Windows.
    add_advancement_literals(stage, report)
    add_bitmap_font(stage, report)
    add_json_book_tree(stage, report, ROOT / "work" / "patchouli_vi", "patchouli_vi")
    add_json_book_tree(stage, report, ROOT / "work" / "patchouli_root_vi", "patchouli_root_vi")
    add_json_book_tree(stage, report, ROOT / "work" / "tconstruct_vi", "tconstruct_vi")
    add_json_book_tree(stage, report, ROOT / "work" / "extra_guides_vi", "extra_guides_vi")
    # Case-normalize only after every family and literal overlay has merged.
    apply_runtime_locale_casing(stage)
    if all_errors:
        for source_name, error in all_errors[:200]:
            print(f"{source_name}\t{error.code}\t{error.key}\t{error.detail}")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1
    pack_meta = {
        "pack": {"pack_format": 3, "description": "Divine Journey 2 v2.23.4 - Việt hoá Quest, UI, sách và tooltip"},
        "language": {"vi_vn": {"name": "Tiếng Việt", "region": "Việt Nam", "bidirectional": False}},
    }
    (stage / "pack.mcmeta").write_text(json.dumps(pack_meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(path.relative_to(stage).as_posix(), date_time=(2026, 8, 24, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(output) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"Corrupt zip member: {bad}")
        names = archive.namelist()
        if len(names) != len({name.casefold() for name in names}):
            raise RuntimeError("ZIP contains case-insensitive path collisions")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"BUILT {output} bytes={output.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
