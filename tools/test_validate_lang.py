from build_pack import SPECS, load_spec_source
from validate_lang import parse_lang_text, validate
from pathlib import Path
import zipfile
import json

SRC_TEXT = """dj2.quest.db.1.title=Laser crafting advantages
dj2.quest.db.1.desc=Craft a §6Stellar Capacitor§r!%n%nIt is 50%% faster.
"""

GOOD_TEXT = """dj2.quest.db.1.title=Lợi thế khi craft bằng laser
dj2.quest.db.1.desc=Chế tạo một §6Stellar Capacitor§r!%n%nNó nhanh hơn 50%%.
"""


def test_passes_on_good_translation():
    src, src_dupes = parse_lang_text(SRC_TEXT)
    tgt, tgt_dupes = parse_lang_text(GOOD_TEXT)
    assert validate(src, tgt, protected={"Stellar Capacitor"}, source_duplicates=src_dupes, target_duplicates=tgt_dupes) == []


def test_catches_missing_key():
    src, _ = parse_lang_text(SRC_TEXT)
    tgt, _ = parse_lang_text("dj2.quest.db.1.title=Lợi thế khi craft bằng laser\n")
    assert any(e.code == "MISSING_KEY" for e in validate(src, tgt, set()))


def test_catches_extra_key():
    src, _ = parse_lang_text(SRC_TEXT)
    tgt, _ = parse_lang_text(GOOD_TEXT + "dj2.quest.db.999.title=thừa\n")
    assert any(e.code == "EXTRA_KEY" for e in validate(src, tgt, set()))


def test_catches_duplicate_key():
    _, dupes = parse_lang_text(GOOD_TEXT + "dj2.quest.db.1.title=trùng\n")
    src, _ = parse_lang_text(SRC_TEXT)
    tgt, _ = parse_lang_text(GOOD_TEXT)
    assert any(e.code == "DUPLICATE_KEY" for e in validate(src, tgt, set(), target_duplicates=dupes))


def test_catches_newline_count_change():
    src, _ = parse_lang_text(SRC_TEXT)
    tgt, _ = parse_lang_text(GOOD_TEXT.replace("%n%n", " "))
    assert any(e.code == "PCT_N_COUNT" for e in validate(src, tgt, set()))


def test_catches_bare_percent():
    src, _ = parse_lang_text(SRC_TEXT)
    tgt, _ = parse_lang_text(GOOD_TEXT.replace("50%%", "50%"))
    assert any(e.code == "FORMAT_TOKENS" for e in validate(src, tgt, set()))


def test_catches_color_code_change():
    src, _ = parse_lang_text(SRC_TEXT)
    tgt, _ = parse_lang_text(GOOD_TEXT.replace("§6", "").replace("§r", ""))
    assert any(e.code == "COLOR_CODES" for e in validate(src, tgt, set()))


def test_catches_translated_item_name():
    src, _ = parse_lang_text(SRC_TEXT)
    tgt, _ = parse_lang_text(GOOD_TEXT.replace("Stellar Capacitor", "Tụ Điện Sao"))
    assert any(e.code == "PROTECTED_TERM" for e in validate(src, tgt, {"Stellar Capacitor"}))


def test_catches_lost_url():
    src, _ = parse_lang_text("k=Đọc https://example.com/a\n")
    tgt, _ = parse_lang_text("k=Đọc hướng dẫn\n")
    assert any(e.code == "URL_LOST" for e in validate(src, tgt, set()))


def test_url_stops_before_literal_minecraft_newline():
    src, _ = parse_lang_text("k=Xem https://example.com/issues%n(This link)\n")
    tgt, _ = parse_lang_text("k=Xem https://example.com/issues%n(Liên kết này)\n")
    assert not any(e.code == "URL_LOST" for e in validate(src, tgt, set()))


def test_betterquesting_gui_and_quests_share_one_locale_resource():
    spec = next(s for s in SPECS if s["source"] == "betterquesting-quests.lang")
    assert spec["namespace"] == "betterquesting"
    assert spec["english_locale"] == "en_US"
    assert "betterquesting-gui.json" in spec["translations"]
    assert "orphans.json" in spec["translations"]


def test_betterquesting_composite_source_contains_quest_and_gui_keys():
    source, duplicates = load_spec_source("betterquesting-quests.lang")
    assert len(source) == 3532 + 186
    assert not duplicates


def test_pack_metadata_is_ascii_safe_for_legacy_minecraft():
    metadata = json.dumps({"pack": {"pack_format": 3, "description": "DJ2 Việt hoá"}}, ensure_ascii=True)
    assert metadata.isascii()


def test_build_specs_do_not_overwrite_the_same_resource_path_case_insensitively():
    paths = [f"assets/{s['namespace']}/lang/{s['english_locale']}.lang".casefold() for s in SPECS]
    assert len(paths) == len(set(paths))


def test_catches_raw_newline_that_truncates_the_line():
    """A real newline inside a value ends the .lang line: everything after it is lost."""
    src, _ = parse_lang_text("a.b.info=First part\\n\\nSecond part\n")
    broken = {"a.b.info": "Phan mot" + chr(10) + "Phan hai"}
    assert "RAW_NEWLINE" in [e.code for e in validate(src, broken, protected=())]
    good = {"a.b.info": "Phan mot\\n\\nPhan hai"}
    assert validate(src, good, protected=()) == []


def test_catches_cjk_debris_from_machine_translation():
    src, _ = parse_lang_text("a.b.info=a medium\n")
    assert validate(src, {"a.b.info": "lam moi gioi"}, protected=()) == []
    debris = {"a.b.info": "lam moi " + chr(0x4ecb) + chr(0x8d28)}
    assert "CJK_CHAR" in [e.code for e in validate(src, debris, protected=())]


def test_registry_names_are_guarded_here_not_in_the_other_validator():
    """This module owns the 21 real registry names; the other validator matched 0."""
    src, _ = parse_lang_text("item.roots.roots_guide.name=The Magic of the Wilds\n")
    kept = {"item.roots.roots_guide.name": "The Magic of the Wilds"}
    assert validate(src, kept, protected=()) == []
    translated = {"item.roots.roots_guide.name": "Ma Thu" + chr(0x1ead) + "t Hoang Da"}
    assert "REGISTRY_NAME_TRANSLATED" in [e.code for e in validate(src, translated, protected=())]


def test_gui_labels_ending_in_name_are_not_registry_names():
    """624 of the 919 shipped `.name` keys are deliberately Vietnamese GUI labels."""
    src, _ = parse_lang_text("gui.appliedenergistics2.security.craft.name=Craft\n")
    label = {"gui.appliedenergistics2.security.craft.name": "Ch" + chr(0x1ebf) + " t" + chr(0x1ea1) + "o"}
    assert "REGISTRY_NAME_TRANSLATED" not in [e.code for e in validate(src, label, protected=())]
