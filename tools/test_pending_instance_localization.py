import importlib.util
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PendingInstanceLocalizationTests(unittest.TestCase):
    def test_requious_locale_is_built_with_all_ten_reviewed_keys(self):
        build_pack = load_module("build_pack_pending", ROOT / "tools" / "build_pack.py")
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "pack.zip"
            stage = Path(td) / "stage"
            self.assertEqual(build_pack.build(output=output, stage=stage), 0)
            with zipfile.ZipFile(output) as zf:
                text = zf.read("assets/requious_frakto/lang/vi_vn.lang").decode("utf-8")
        entries = dict(line.split("=", 1) for line in text.splitlines() if line and not line.startswith("#"))
        self.assertEqual(len(entries), 10)
        self.assertEqual(entries["requious.jei.recipe.configure"], "Cấu hình Block")
        self.assertEqual(entries["requious.jei.recipe.explore_world"], "Khám phá thế giới")

    def test_enderio_soulbound_description_is_vietnamese(self):
        translated = json.loads((ROOT / "work" / "translated" / "enchantment_descriptions_all.json").read_text(encoding="utf-8"))
        self.assertEqual(translated["enchantment.enderio.soulbound.desc"], "Vật phẩm không rơi ra khi chết.")

    def test_selected_quest_prose_titles_are_translated(self):
        expected = {
            "dj2.quest.db.6.title": "Collector — Nhà sưu tầm",
            "dj2.quest.db.302.title": "Gia nhập câu lạc bộ Golden Club",
            "dj2.quest.db.428.title": "Tự động hóa Compressor",
            "dj2.quest.db.443.title": "Crafting Table áp chót",
            "dj2.quest.db.489.title": "Yttrium quăng bay",
            "dj2.quest.db.520.title": "Cadmium chuẩn Chad",
            "dj2.quest.db.640.title": "The Ender-est Ender Pearl — Viên Ender Pearl tận cùng nhất",
        }
        found = {}
        for path in sorted((ROOT / "work" / "translated").glob("ql_*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            for key in expected:
                if key in data:
                    found[key] = data[key]
        self.assertEqual(found, expected)

    def test_client_bundle_contains_localized_menu_and_defaults(self):
        bundle = load_module("build_client_pending", ROOT / "tools" / "build_client_bundle.py")
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "client.zip"
            entries = bundle.build(output)
            required = {
                "config/CustomMainMenu/mainmenu.json",
                "resources/mainmenu/singleplayer.png",
                "resources/mainmenu/multiplayer.png",
                "resources/mainmenu/options.png",
                "resources/mainmenu/mods.png",
                "resources/mainmenu/version_history.png",
                "resources/mainmenu/quit_game.png",
                "config/defaultoptions/options.txt",
                "config/crash_assistant/config.toml",
            }
            self.assertTrue(required.issubset(entries))
            with zipfile.ZipFile(output) as zf:
                menu = json.loads(zf.read("config/CustomMainMenu/mainmenu.json").decode("utf-8"))
                options = zf.read("config/defaultoptions/options.txt").decode("utf-8-sig")
                crash = zf.read("config/crash_assistant/config.toml").decode("utf-8-sig")
            # CustomMainMenu decodes these with the platform default charset, not UTF-8,
            # so any diacritic renders as mojibake on the main menu. They stay ASCII.
            self.assertEqual(menu["buttons"]["discord"]["tooltip"], "Tham gia may chu Discord cua Divine Journey 2!")
            self.assertEqual(menu["buttons"]["language"]["tooltip"], "Ngon ngu")
            self.assertEqual(menu["labels"]["modsloaded"]["text"], "#modsloaded# Mod da tai")
            self.assertIn('resourcePacks:["DJ2_Viet_Hoa_2.23.4.zip"]', options)
            self.assertIn("lang:vi_vn", options)
            # The pack supplies its own bitmap font pages; forcing unifont would
            # replace them with the coarser vanilla 8x8 glyphs.
            # 1.12.2 draws part of Vietnamese through ascii.png and the rest
            # through unicode pages when this is false, mixing two sizes in one
            # word. The pack owns both ASCII and Vietnamese unicode pages, so the
            # uniform unicode rendering path is required.
            self.assertIn("forceUnicodeFont:true", options)
            self.assertNotIn("forceUnicodeFont:false", options)
            self.assertIn('default_lang = "vi_vn"', crash)

    def test_localized_menu_sprites_preserve_geometry(self):
        from PIL import Image
        expected = {
            "singleplayer.png": (224, 54),
            "multiplayer.png": (224, 54),
            "options.png": (224, 54),
            "mods.png": (224, 54),
            "version_history.png": (224, 54),
            "quit_game.png": (100, 126),
        }
        base = ROOT / "work" / "client_overlay_vi" / "resources" / "mainmenu"
        for name, size in expected.items():
            with Image.open(base / name) as image:
                self.assertEqual(image.size, size)

    def test_ftbutilities_merge_changes_only_reviewed_text_fields(self):
        merge = load_module("merge_ftb_pending", ROOT / "tools" / "merge_instance_ftbutilities.py")
        live = ROOT / "work" / "testdata" / "ftbutilities_live.cfg"
        canonical = ROOT / "source" / "server_shared" / "config" / "ftbutilities.cfg"
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "ftbutilities.cfg"
            changed = merge.merge(live, canonical, output)
            self.assertEqual(changed, {"motd"})
            self.assertEqual(merge.without_reviewed_text(output), merge.without_reviewed_text(live))
            text = output.read_text(encoding="utf-8-sig")
            self.assertNotIn("Hello player!", text)
            self.assertIn("/tpa", text)


class InstalledInstanceTests(unittest.TestCase):
    """Guards on the live instance, where the shipped artifacts actually land.

    The build can be perfect and the player still sees English or a stale font,
    because what matters at runtime is the bytes sitting in the instance. These
    tests read the installed instance directly and are skipped when it is absent.
    """

    INSTANCE = Path(
        r"C:/Users/Administrator/AppData/Roaming/ElyPrismLauncher"
        r"/instances/Divine Journey 2/minecraft"
    )

    def setUp(self):
        if not self.INSTANCE.is_dir():
            self.skipTest("DJ2 instance not installed on this machine")

    def test_installed_resource_pack_matches_the_built_pack(self):
        """A stale pack in the instance means the player runs an older font."""
        built = ROOT / "build" / "DJ2_Viet_Hoa_2.23.4.zip"
        installed = self.INSTANCE / "resourcepacks" / "DJ2_Viet_Hoa_2.23.4.zip"
        self.assertTrue(installed.is_file(), "resource pack is not installed")
        self.assertEqual(
            hashlib.sha1(installed.read_bytes()).hexdigest(),
            hashlib.sha1(built.read_bytes()).hexdigest(),
            "the installed resource pack is not the one that was just built; "
            "reinstall it or the player keeps the previous font",
        )

    def test_client_bundle_was_not_extracted_into_a_subdirectory(self):
        """The bundle must land at the instance root, not inside another folder.

        Extracting it one level down leaves a full shadow copy of config/ and
        resourcepacks/ that Minecraft never reads, so translations look applied
        while the game keeps loading the untranslated originals. coremods/ is the
        specific trap: it already exists, so an extract-here lands silently.
        """
        strays = []
        for candidate in ("coremods", "mods", "config", "scripts", "resources"):
            marker = self.INSTANCE / candidate / "config" / "defaultoptions" / "options.txt"
            if marker.is_file():
                strays.append(str(marker.relative_to(self.INSTANCE)).replace("\\", "/"))
        self.assertEqual(
            strays,
            [],
            "the client bundle was extracted into a subdirectory instead of the "
            "instance root; these shadow copies are dead files: " + ", ".join(strays),
        )

    def test_every_options_file_in_the_instance_forces_the_unicode_font(self):
        """A single stale options.txt can silently restore the mixed-size font.

        Only live options files count. Backup folders keep the pre-localization
        originals on purpose, and that is exactly what a rollback needs.
        """
        offenders = []
        for options in self.INSTANCE.rglob("options.txt"):
            relative = options.relative_to(self.INSTANCE)
            if any(part.startswith(".") or "backup" in part.lower() for part in relative.parts):
                continue
            text = options.read_text(encoding="utf-8", errors="replace")
            if "forceUnicodeFont:false" in text:
                offenders.append(str(relative).replace("\\", "/"))
        self.assertEqual(
            offenders,
            [],
            "these options files still disable the unicode font, which mixes "
            "ascii.png and the pack's unicode pages: " + ", ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
