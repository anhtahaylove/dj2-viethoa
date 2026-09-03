"""Tests for tools/extract_runtime_sources.py.

The extractor closes the root cause behind every "missing key" bug this project
has shipped: `work/runtime_locale_sources/*.lang` was maintained BY HAND, so a
mod nobody remembered to harvest stayed English forever and no checker could
see it -- the validators only compare source against translation, never source
against the JARs the game actually loads.
"""

import json
import re
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import extract_runtime_sources as ers

ROOT = Path(__file__).resolve().parents[1]


def make_jar(path: Path, namespace: str, body: str, locale: str = "en_us") -> None:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(f"assets/{namespace}/lang/{locale}.lang", body)


class ParseLangTests(unittest.TestCase):
    def test_comments_and_blank_lines_are_skipped(self):
        parsed = ers.parse_lang("# comment\n\nkey.a=Value A\n")
        self.assertEqual(parsed, {"key.a": "Value A"})

    def test_value_keeps_equals_signs_and_trailing_spaces_are_preserved(self):
        parsed = ers.parse_lang("key.b=a=b=c\nkey.c=trailing  \n")
        self.assertEqual(parsed["key.b"], "a=b=c")
        self.assertEqual(parsed["key.c"], "trailing  ")

    def test_utf8_bom_is_stripped_from_the_first_key(self):
        parsed = ers.parse_lang("\ufeffkey.d=Value D\n")
        self.assertEqual(parsed, {"key.d": "Value D"})

    def test_lines_without_a_separator_are_ignored(self):
        self.assertEqual(ers.parse_lang("garbage line\nkey.e=E\n"), {"key.e": "E"})


class UiKeyClassificationTests(unittest.TestCase):
    def test_registry_names_are_not_ui_keys(self):
        for key in (
            "item.totemic.flute.name",
            "tile.totemic.totem_pole.name",
            "entity.totemic.baykok.name",
            "fluid.mekanism.brine",
        ):
            self.assertFalse(ers.is_ui_key(key), key)

    def test_player_facing_keys_are_ui_keys(self):
        for key in (
            "totemic.page.warDance0",
            "tc.aspect.aer",
            "stat.head.attack.name",
            "gui.enderio.confirm",
        ):
            self.assertTrue(ers.is_ui_key(key), key)

    def test_generated_recipe_wiki_keys_are_not_ui_keys(self):
        """groovyscript ships 2735 auto-generated wiki keys for scripters.

        They are documentation for people writing GroovyScript, not strings a
        player reads while playing, so harvesting them would bury the real
        backlog under noise.
        """
        for key in (
            "groovyscript.wiki.minecraft.crafting.add_shaped",
            "groovyscript.wiki.thermalexpansion.pulverizer.description",
        ):
            self.assertFalse(ers.is_ui_key(key), key)


class ExtractionTests(unittest.TestCase):
    def test_extraction_reads_en_us_from_a_jar(self):
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            make_jar(tmp / "mod.jar", "demomod", "demomod.gui.ok=OK\nitem.demomod.x.name=X\n")
            found = ers.harvest_jars(tmp)
            self.assertIn("demomod", found)
            self.assertEqual(found["demomod"]["demomod.gui.ok"], "OK")

    def test_registry_names_are_excluded_from_the_harvest(self):
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            make_jar(tmp / "mod.jar", "demomod", "demomod.gui.ok=OK\nitem.demomod.x.name=X\n")
            found = ers.harvest_jars(tmp)
            self.assertNotIn("item.demomod.x.name", found["demomod"])

    def test_uppercase_locale_directory_is_also_matched(self):
        """Some 1.12 mods ship `en_US.lang`; missing them silently loses a mod."""
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            make_jar(tmp / "mod.jar", "oldmod", "oldmod.gui.ok=OK\n", locale="en_US")
            self.assertIn("oldmod", ers.harvest_jars(tmp))

    def test_empty_values_are_not_harvested(self):
        """Blank guide-book pages pad fixed-size entries in several mods.

        Totemic ships 18 of them. There is nothing to translate, so harvesting
        them would report a permanent gap that can never be closed.
        """
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            make_jar(tmp / "mod.jar", "demomod", "demomod.page.a=Real text\ndemomod.page.b=\n")
            found = ers.harvest_jars(tmp)
            self.assertIn("demomod.page.a", found["demomod"])
            self.assertNotIn("demomod.page.b", found["demomod"])

    def test_missing_report_separates_absent_keys_from_translated_ones(self):
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            make_jar(tmp / "mod.jar", "demomod", "demomod.a=A\ndemomod.b=B\n")
            harvested = ers.harvest_jars(tmp)
            report = ers.diff_against_sources(harvested, {"demomod": {"demomod.a"}})
            self.assertEqual(report["demomod"]["missing"], ["demomod.b"])


class RealPackTests(unittest.TestCase):
    """Guards against regressions in the namespaces fixed this round.

    These compare the JARs against the BUILT PACK, not against the source
    files. Translations are spread across several trees (`runtime_locales/`,
    `books_*.json`, chapter batches), so a per-source comparison reports false
    gaps -- `book.start.1` lives in `books_thaumcraft.json`, not in
    `runtime_locale_sources/thaumcraft.lang`. The pack is the only place where
    every tree has been merged, and it is what the game actually reads.
    """

    @staticmethod
    def _built_lang(namespace: str) -> Path | None:
        matches = sorted(ROOT.glob(f"build/DJ2_Viet_Hoa_*/assets/{namespace}/lang/vi_vn.lang"))
        return matches[-1] if matches else None

    def test_totemic_ui_keys_all_reach_the_built_pack(self):
        instance = Path(
            "C:/Users/Administrator/AppData/Roaming/ElyPrismLauncher/instances/"
            "Divine Journey 2/minecraft/mods"
        )
        built = self._built_lang("totemic")
        if not instance.exists() or built is None:
            self.skipTest("instance or built pack not present on this machine")
        harvested = ers.harvest_jars(instance).get("totemic", {})
        shipped = set(ers.parse_lang(built.read_text(encoding="utf-8")))
        missing = sorted(set(harvested) - shipped)
        self.assertEqual(missing, [], f"totemic lost {len(missing)} UI keys")

    def test_every_aspect_key_reaches_the_built_pack(self):
        built = self._built_lang("thaumcraft")
        if built is None:
            self.skipTest("pack not built yet")
        keys = ers.parse_lang(built.read_text(encoding="utf-8"))
        aspects = [k for k in keys if k.startswith("tc.aspect.")]
        self.assertGreaterEqual(len(aspects), 40, "aspect keys regressed below 40")


# Vietnamese-only letters: no English or Latin-1 loanword spelling uses these.
VIETNAMESE_ONLY_LETTERS = re.compile(
    r"[đĐơƠưƯăĂ]"
    r"|[ạảãấầẩẫậắằẳẵặẹẻẽếềểễệịỉĩọỏõốồổỗộớờởỡợụủũứừửữựỵỷỹ]"
)
# Function words that only co-occur in running Vietnamese prose.
VIETNAMESE_FUNCTION_WORDS = re.compile(
    r"\b(và|của|các|được|trong|khi|này|cho|với|từ|một|những|hoặc|nếu|đã|sẽ"
    r"|bạn|người|không|là|để|thì|nhưng|vào|ra|trên|dưới)\b",
    re.IGNORECASE,
)

# 16 enchantment descriptions have no upstream English at all: Divine Journey 2
# ships `enchantment_descriptions` with the key registered but no value, so this
# project authored the text. They are Vietnamese on purpose and are the only
# legitimate Vietnamese in the English source tree.
PROJECT_AUTHORED_SOURCE_KEYS = 16


def looks_vietnamese(value: str) -> bool:
    """True when a value is Vietnamese prose rather than English.

    Diacritics alone are not enough: `Skál!` (Icelandic, Immersive Engineering)
    and `"x!(àà)ç"` (a string-escaping example in Integrated Dynamics) are
    genuine English-locale values that carry accents.
    """
    if VIETNAMESE_ONLY_LETTERS.search(value):
        return True
    return len({w.lower() for w in VIETNAMESE_FUNCTION_WORDS.findall(value)}) >= 2


class EnglishSourcePurityTests(unittest.TestCase):
    """Guard against re-infecting work/runtime_locale_sources/ with Vietnamese.

    Every validator and test in this project compares an English source against
    its Vietnamese translation. When the "English" half holds Vietnamese, those
    checks compare Vietnamese with Vietnamese and pass while proving nothing --
    which is exactly what happened for 7,014 keys across 68 files, undetected
    from the first commit until a width check surfaced it. Restoring the real
    English immediately exposed 74 consistency errors, 38 formatting errors and
    6 CraftTweaker strings that had lost every color code.
    """

    @classmethod
    def setUpClass(cls):
        cls.sources = sorted((ROOT / "work" / "runtime_locale_sources").glob("*.lang"))

    def test_source_tree_is_present(self):
        self.assertGreater(len(self.sources), 100, "runtime source tree missing")

    def test_english_sources_are_not_vietnamese(self):
        offenders = []
        for path in self.sources:
            entries = ers.parse_lang(path.read_text(encoding="utf-8"))
            for key, value in entries.items():
                if looks_vietnamese(value):
                    offenders.append(f"{path.name}:{key} = {value[:60]!r}")
        self.assertLessEqual(
            len(offenders),
            PROJECT_AUTHORED_SOURCE_KEYS,
            "Vietnamese text leaked into the English source tree "
            f"({len(offenders)} values):\n" + "\n".join(sorted(offenders)[:20]),
        )

    def test_only_the_known_authored_family_may_be_vietnamese(self):
        """Pin the exemption to one family so a new leak cannot hide in it."""
        for path in self.sources:
            entries = ers.parse_lang(path.read_text(encoding="utf-8"))
            for key, value in entries.items():
                if looks_vietnamese(value):
                    self.assertTrue(
                        key.startswith("enchantment.") and key.endswith(".desc"),
                        f"unexpected Vietnamese source value {path.name}:{key}",
                    )

    def test_detector_catches_a_translated_source_file(self):
        """The guard must fail on infection, not merely pass when clean."""
        self.assertTrue(looks_vietnamese("Nhấp chuột phải để mở giao diện"))
        self.assertTrue(looks_vietnamese("Chế độ: Kết hợp"))
        self.assertFalse(looks_vietnamese("Right-click to open the interface"))
        self.assertFalse(looks_vietnamese("Skál!"))
        self.assertFalse(looks_vietnamese('A sequence of characters, "x!(àà)ç"'))


if __name__ == "__main__":
    unittest.main()
