"""Guide-book prose must actually be Vietnamese, scanned wholesale.

The other suites check named keys, so they only catch regressions in strings
somebody already noticed. Two whole families slipped through that way:

  * Patchouli `pages[].blurb/breed/tame` — rendered on the entry page, but the
    translator only walked `text`, so mysticalworld's creature guide shipped
    29 English lines.
  * The Tinkers' Construct book under `assets/tconstruct/book/vi_vn/` — a
    separate tree from `assets/tconstruct/lang/`, so translating the .lang left
    46 book strings in English.

Both are scanned here by walking every value, not by listing keys, so a newly
added entry with untranslated prose fails without anyone having to notice it.

Detection rule: a value with no Vietnamese diacritics that reads as English
grammar (>=2 common function words). Proper nouns are unaffected — "Glass
Sword" or "Blaze Powder" carry no function words and stay English by policy.
"""
from __future__ import annotations

import json
import re
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "build" / "DJ2_Viet_Hoa_2.23.4.zip"

VIETNAMESE = re.compile(
    "[ăâđêôơưĂÂĐÊÔƠƯáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩị"
    "óòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ"
    "ÁÀẢÃẠẮẰẲẴẶẤẦẨẪẬÉÈẺẼẸẾỀỂỄỆÍÌỈĨỊ"
    "ÓÒỎÕỌỐỒỔỖỘỚỜỞỠỢÚÙỦŨỤỨỪỬỮỰÝỲỶỸỴ]"
)
WORD = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
# Patchouli macros ($(l:...), $(br2)) and .lang format tokens are not prose.
MARKUP = re.compile(r"\$\([^)]*\)|%[sdn%]")

FUNCTION_WORDS = frozenset(
    """the and to of in on for with from into by at is are was were be been being
    this that these those you your it its as or not can will should must would
    could right left click hold press use make place find get has have after
    before when while if then each all any some per more less than a an there
    here how where which what who why does do did through without within
    between over under above below around once first second another them their
    they""".split()
)

# Fields Patchouli renders to the player inside a page. `blurb`, `breed` and
# `tame` belong to animal_spawn_info pages and are as visible as `text`.
PROSE_FIELDS = frozenset(
    {"text", "blurb", "breed", "tame", "title", "description", "caption", "subtitle"}
)


def is_title_case_name(value: str) -> bool:
    """True for proper-noun titles like 'Rite of the Tough and Pure'.

    Policy keeps names English so players can search JEI and the wiki. A name
    capitalises every word except the small joining words ('of', 'the', 'and'),
    whereas a sentence leaves its ordinary nouns and verbs in lower case
    ('Can be used as a shield'). That difference is what separates the two.
    """
    words = WORD.findall(MARKUP.sub(" ", value))
    if not words:
        return False
    content = [w for w in words if w.lower() not in FUNCTION_WORDS]
    if not content:
        return False
    return all(w[0].isupper() for w in content)


def reads_as_english(value: str) -> bool:
    """True when a string looks like untranslated English prose."""
    if VIETNAMESE.search(value):
        return False
    words = [w.lower() for w in WORD.findall(MARKUP.sub(" ", value))]
    if len(words) < 3:
        return False
    if sum(word in FUNCTION_WORDS for word in words) < 2:
        return False
    # Proper names are preserved on purpose and must not be reported.
    return not is_title_case_name(value)


def walk(node, path="", in_pages=False):
    """Yield (path, string) for every string value, tracking `pages` descent."""
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}" if path else key
            yield from walk(value, child, in_pages or key == "pages")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from walk(value, f"{path}[{index}]", in_pages)
    elif isinstance(node, str):
        yield path, node


def leaf_name(path: str) -> str:
    return path.split(".")[-1].split("[")[0]


class QuestBookTerminologyTests(unittest.TestCase):
    """The generic quest-book UI noun should read Vietnamese, not English.

    "Better Questing" and "BQTweaker" are proper names that stay English, and
    "/bq_admin default load" is a command, but the thing a player opens and
    reloads is a generic object — leaving it as "Questbook" mid-sentence is the
    mixed-language prose this pack exists to remove.
    """

    def test_bq_introduction_quest_uses_vietnamese_term(self):
        text = json.loads(
            (ROOT / "work" / "translated" / "ql_00.json").read_text(encoding="utf-8")
        )["dj2.quest.db.471.desc"]
        self.assertNotIn("Questbook", text)
        self.assertIn("Sổ Nhiệm Vụ", text)
        # The command and the proper names must survive the rewording untouched.
        self.assertIn("/bq_admin default load", text)
        self.assertIn("Better Questing", text)
        self.assertIn("BQTweaker", text)


class PatchouliPageProseTests(unittest.TestCase):
    """Every rendered Patchouli page field ships in Vietnamese."""

    def test_no_english_prose_in_rendered_page_fields(self):
        offenders = []
        with zipfile.ZipFile(PACK) as zf:
            names = [
                n
                for n in zf.namelist()
                if "/patchouli_books/" in n and "/vi_vn/" in n and n.endswith(".json")
            ]
            self.assertTrue(names, "no Vietnamese Patchouli entries found in the pack")
            for name in names:
                data = json.loads(zf.read(name).decode("utf-8"))
                for path, value in walk(data):
                    # `pages_EXAMPLE_OF_EDITABLE` is upstream's dead sample block:
                    # Patchouli only renders `pages`, so it is not player-facing.
                    if not path.startswith("pages["):
                        continue
                    if leaf_name(path) in PROSE_FIELDS and reads_as_english(value):
                        offenders.append(f"{name} :: {path} = {value[:90]}")
        self.assertEqual(
            [], offenders, "untranslated Patchouli page prose:\n" + "\n".join(offenders)
        )


class TinkersBookProseTests(unittest.TestCase):
    """The Tinkers' book tree is separate from its .lang and needs its own check."""

    def test_no_english_prose_in_tinkers_book(self):
        offenders = []
        with zipfile.ZipFile(PACK) as zf:
            names = [n for n in zf.namelist() if "/tconstruct/book/vi_vn/" in n]
            self.assertTrue(names, "Tinkers' Vietnamese book missing from the pack")
            for name in names:
                raw = zf.read(name).decode("utf-8")
                if name.endswith(".json"):
                    pairs = list(walk(json.loads(raw)))
                elif name.endswith(".lang"):
                    pairs = [
                        tuple(line.split("=", 1))
                        for line in raw.splitlines()
                        if line and not line.lstrip().startswith("#") and "=" in line
                    ]
                else:
                    continue
                for key, value in pairs:
                    if reads_as_english(value):
                        offenders.append(f"{name} :: {key} = {value[:90]}")
        self.assertEqual(
            [], offenders, "untranslated Tinkers' book prose:\n" + "\n".join(offenders)
        )


class ProseDetectorTests(unittest.TestCase):
    """The detector itself must not fire on names we deliberately keep English."""

    def test_flags_untranslated_sentences(self):
        self.assertTrue(reads_as_english("Can be used as a shield"))
        self.assertTrue(reads_as_english("The drops depend on the colour of the sprout!"))

    def test_ignores_preserved_proper_nouns_and_vietnamese(self):
        for keep in (
            "Glass Sword",
            "Rite of the Tough and Pure",
            "Blaze Powder",
            "Hounds of the Hunt",
            "The Gate of the Fold",
        ):
            self.assertFalse(reads_as_english(keep), f"would wrongly flag {keep!r}")
        self.assertFalse(reads_as_english("Có thể dùng như một shield"))

    def test_sentence_beginning_with_a_capital_is_still_prose(self):
        # A name capitalises its content words; a sentence does not, so the
        # leading capital alone must never buy an exemption.
        self.assertTrue(reads_as_english("Tool remains in your inventory after death"))
        self.assertTrue(reads_as_english("Adding more Obsidian increases the chance"))


if __name__ == "__main__":
    unittest.main()
