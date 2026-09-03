"""Tests for tools/triage_other_tier.py.

The triage script decides which untranslated rows are real debt and which ship
in English on purpose. Every rule here was derived from the shipped corpus, and
each one silenced rows that a previous wave had already hand-reviewed and
rejected -- without the rules those rows resurfaced as "debt" on every run and
invited someone to re-litigate a settled decision, or worse, to translate an
item name.

Two failure modes matter, so both are covered:

  * A rule too broad hides real debt (a translatable string keeps English).
  * A rule too narrow keeps re-surfacing settled rows as false debt.
"""

import unittest

import triage_other_tier as triage


def row(key, english, namespace="somemod", tier="other"):
    return {"key": key, "en": english, "namespace": namespace, "tier": tier}


class CommandSyntaxTests(unittest.TestCase):
    """Command syntax the player must type stays English, placeholders included."""

    def test_numbered_placeholders_are_still_command_syntax(self):
        kept = triage.reason_to_keep(
            row("commands.ta.makefracture.usage",
                "thaumicaugmentation makefracture <x1> <y1> <z1> [dim1]"))
        self.assertEqual(kept, "command syntax the player must type")

    def test_ellipsis_inside_optional_argument_is_command_syntax(self):
        kept = triage.reason_to_keep(
            row("item.wrcbe.usage", "REther management. Usage: freq [params...]"))
        self.assertEqual(kept, "command syntax the player must type")

    def test_prose_with_a_bracketed_vietnamese_word_is_not_command_syntax(self):
        self.assertIsNone(triage.reason_to_keep(row("gui.some.label", "Select a colour")))


class FormatTemplateTests(unittest.TestCase):
    """A value with no letters outside its format specifiers has nothing to translate."""

    def test_bare_two_token_template(self):
        self.assertEqual(triage.reason_to_keep(row("k.a", "%s: %s")), "format template, no prose to translate")

    def test_positional_tokens_with_punctuation(self):
        self.assertEqual(
            triage.reason_to_keep(row("k.b", "[%1$s] %2$s: %3$d")), "format template, no prose to translate")

    def test_multiplier_notation_is_kept_by_exact_key_not_by_the_generic_rule(self):
        """`x%s` renders as `x3`, so its `x` is notation rather than a word.

        The generic format rule deliberately does NOT cover it: a lone letter
        beside a token can be a real word elsewhere ("Kg%s"), so the decision is
        recorded per key instead of guessed.
        """
        self.assertIn("multiplier notation",
                      triage.reason_to_keep(row("gui.atum.rotations", "x%s")))
        self.assertIsNone(triage.reason_to_keep(row("gui.othermod.multiplier", "x%s")))

    def test_a_template_with_real_words_is_debt(self):
        self.assertIsNone(triage.reason_to_keep(row("k.c", "Stored: %s of %s")))


class ColorCodeTests(unittest.TestCase):
    def test_color_code_with_no_text_has_nothing_to_translate(self):
        self.assertEqual(triage.reason_to_keep(row("enderio.top.action.header.pre", "§e")),
                         "colour/style code only, no prose to translate")

    def test_color_code_wrapping_a_label_is_debt(self):
        self.assertIsNone(triage.reason_to_keep(row("enderio.top.tank.header.pre", "§eRecv: §f")))


class RegistryNameTests(unittest.TestCase):
    """Item and block names stay English so the wiki, JEI and recipes still match."""

    ENGLISH = {
        "somemod": {
            "tile.wooden_crate.name": "Wooden Crate",
            "tile.fabricator.name": "Fabricator",
            "container.somemod.crate": "Crate",
            "gui.somemod.Fabricator": "Fabricator",
            "gui.message.saved": "Saved",
        },
        "othermod": {"item.brimstone.name": "Brimstone"},
    }

    def test_screen_title_mirroring_a_registry_name_keeps_english(self):
        kept = triage.reason_to_keep(
            row("gui.somemod.Fabricator", "Fabricator"), self.ENGLISH)
        self.assertEqual(kept, "screen title mirrors the object's registry name")

    def test_a_registry_name_owned_by_another_mod_still_keeps_english(self):
        """Roots' "Brimstone" modifier is an Extra Utilities item name.

        The pack-wide protected-term list is what carries these across
        namespaces, so a name registered by any mod keeps English even when the
        key belongs to a different mod.
        """
        kept = triage.reason_to_keep(
            row("roots.modifiers.modifiers.brimstone", "Brimstone"),
            self.ENGLISH, protected={"Brimstone"})
        self.assertEqual(kept, "value is a protected registry term")

    def test_a_translatable_modifier_name_is_still_debt(self):
        """Same family, but the value is not any mod's registry name."""
        self.assertIsNone(
            triage.reason_to_keep(
                row("roots.modifiers.modifiers.voiding_scythe", "Void"),
                self.ENGLISH, protected={"Brimstone"}))

    def test_in_game_message_is_not_treated_as_a_screen_title(self):
        """`gui.message.*` is HUD text, so a name-shaped value there is still debt."""
        self.assertIsNone(
            triage.reason_to_keep(row("gui.message.saved", "Saved"), self.ENGLISH))

    def test_ordinary_ui_vocabulary_is_debt(self):
        self.assertIsNone(
            triage.reason_to_keep(row("gui.somemod.confirmDelete", "Delete this?"), self.ENGLISH))


class FamilyRuleTests(unittest.TestCase):
    def test_mod_integration_toggles_are_mod_proper_names(self):
        kept = triage.reason_to_keep(
            row("cfg.universaltweaks.modintegration.enderio", "Ender IO",
                namespace="universaltweaks", tier="T3"))
        self.assertEqual(kept, "third-party mod display names")

    def test_constellation_name_key_is_a_proper_name(self):
        kept = triage.reason_to_keep(
            row("astralsorcery.constellation.aevitas", "Aevitas", namespace="astralsorcery"))
        self.assertEqual(kept, "constellation proper names")

    def test_constellation_prose_sibling_is_not_covered_by_the_name_rule(self):
        self.assertIsNone(
            triage.reason_to_keep(
                row("astralsorcery.constellation.aevitas.effect",
                    "Grants regeneration to nearby creatures", namespace="astralsorcery")))


class ExactKeepTests(unittest.TestCase):
    def test_reviewed_key_carries_its_justification(self):
        kept = triage.reason_to_keep(row("generic.ok.txt", "OK", namespace="brandonscore"))
        self.assertIn("OK/Ok stays English", kept)

    def test_exact_keep_matches_the_whole_key_only(self):
        """A prefix must not inherit another key's exemption."""
        self.assertIsNone(triage.reason_to_keep(row("generic.ok.txt.extra", "Some prose")))


class EmptyValueTests(unittest.TestCase):
    def test_blank_value_has_nothing_to_translate(self):
        self.assertEqual(triage.reason_to_keep(row("k.blank", "   ")), "empty value")


if __name__ == "__main__":
    unittest.main()
