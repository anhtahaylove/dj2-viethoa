import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
SPEC = importlib.util.spec_from_file_location("build_pack", ROOT / "tools" / "build_pack.py")
build_pack = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = build_pack
SPEC.loader.exec_module(build_pack)


def parse_lang(text):
    result = {}
    for line in text.splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def locale_member(names, namespace):
    """Resolve the locale casing emitted for a mod's legacy .lang family."""
    candidates = (
        f"assets/{namespace}/lang/vi_vn.lang",
        f"assets/{namespace}/lang/vi_VN.lang",
        f"assets/{namespace}/lang/vi_vn.json",
        f"assets/{namespace}/lang/vi_VN.json",
    )
    return next((name for name in candidates if name in names), None)


class BuildFailureSafetyTests(unittest.TestCase):
    """A failed build must never leave a previous ZIP behind as if it were fresh.

    build() reports validation failure with a return code, but the stale output
    was only removed later, on the success path. A caller that ignores the code
    — as the pipeline scripts chained with && effectively do — would go on to
    hash, publish and serve the *previous* release while believing it shipped
    the new one. That is the silent-stale-artifact failure, so the output is
    removed up front, before any work that can fail.
    """

    def test_build_keeps_the_previous_pack_readable_until_it_is_replaced(self):
        """A build in progress must never blank out the live pack tree.

        The tests that assert against the built pack read
        `build/DJ2_Viet_Hoa_*/assets/...`. When build() deleted that tree up
        front and repopulated it over the next four minutes, a concurrent
        reader saw an empty or half-written pack, so those tests failed with
        "aspect keys regressed" and "totemic lost UI keys" -- failures that
        disappeared on a re-run because nothing was actually wrong with the
        pack. Staging into a `.partial` sibling keeps the previous complete
        pack in place until the new one replaces it in a single step.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / "pack.zip"
            stage = root / "PackTree"
            marker = stage / "assets" / "thaumcraft" / "lang" / "vi_vn.lang"
            marker.parent.mkdir(parents=True)
            marker.write_text("tc.aspect.previous=Bản cũ hoàn chỉnh\n", encoding="utf-8")
            previous = marker.read_text(encoding="utf-8")

            seen = []

            original = build_pack.add_bitmap_font

            def observe(*args, **kwargs):
                # Mid-build: whatever a concurrent reader can see right now.
                seen.append(marker.read_text(encoding="utf-8") if marker.is_file() else None)
                return original(*args, **kwargs)

            build_pack.add_bitmap_font = observe
            try:
                build_pack.build(output=output, stage=stage)
            finally:
                build_pack.add_bitmap_font = original

            self.assertEqual(
                seen,
                [previous],
                "a reader mid-build saw the live pack tree deleted or rewritten; "
                "the previous pack must stay intact until the new one is complete",
            )
            self.assertTrue(marker.is_file(), "the pack tree vanished after the build")

    def test_scratch_tree_is_invisible_to_the_pack_glob(self):
        """Staging must not park a second match under `DJ2_Viet_Hoa_*`.

        The first attempt at the atomic swap named the scratch tree
        `DJ2_Viet_Hoa_2.23.4.partial`. That matches the glob the pack tests use
        AND sorts after the real directory, so their `matches[-1]` resolved to
        the tree still being written -- converting an intermittent race into a
        guaranteed failure. The scratch name must fall outside the pattern.
        """
        import fnmatch

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stage = root / "DJ2_Viet_Hoa_2.23.4"
            marker = stage / "assets" / "thaumcraft" / "lang" / "vi_vn.lang"
            marker.parent.mkdir(parents=True)
            marker.write_text("tc.aspect.previous=x\n", encoding="utf-8")

            during = []
            original = build_pack.add_bitmap_font

            def observe(*args, **kwargs):
                during.extend(
                    p.name
                    for p in root.iterdir()
                    if p.is_dir() and fnmatch.fnmatch(p.name, "DJ2_Viet_Hoa_*")
                )
                return original(*args, **kwargs)

            build_pack.add_bitmap_font = observe
            try:
                build_pack.build(output=root / "pack.zip", stage=stage)
            finally:
                build_pack.add_bitmap_font = original

            self.assertEqual(
                during,
                ["DJ2_Viet_Hoa_2.23.4"],
                "the scratch tree matched the pack glob mid-build, so a reader "
                f"taking the last match would read it: saw {during}",
            )

    def test_failed_build_removes_the_previous_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "stale.zip"
            output.write_bytes(b"PK\x03\x04 previous release bytes")
            before = output.read_bytes()

            def explode(*args, **kwargs):
                raise RuntimeError("validation failed")

            original = build_pack.add_bitmap_font
            build_pack.add_bitmap_font = explode
            try:
                with self.assertRaises(RuntimeError):
                    # Keep the scratch tree in the temp dir as well: with no
                    # explicit stage it defaults into the real build/, and
                    # this test makes the build explode on purpose, so a
                    # .partial- tree was left behind in the live output.
                    build_pack.build(output=output, stage=Path(td) / "stage")
            finally:
                build_pack.add_bitmap_font = original

            self.assertFalse(
                output.exists() and output.read_bytes() == before,
                "a failed build left the previous artifact in place, where the "
                "next pipeline step would hash and publish it as the new release",
            )


class BuildPackTests(unittest.TestCase):
    def test_progression_priority_500_runtime_prose_gaps_are_translated_and_packaged(self):
        """Every approved high-confidence player-facing row must ship in vi_vn.

        The frozen manifest records the exact approved boundary so this regression
        remains reproducible without relying on a user-specific temporary file.
        """
        manifest_path = ROOT / "work" / "approved_progression_500.json"
        self.assertTrue(manifest_path.is_file(), f"missing audit manifest: {manifest_path}")
        expected = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(len(expected), 500)

        untranslated = []
        with zipfile.ZipFile(build_pack.ZIP_OUT) as archive:
            members = set(archive.namelist())
            cache = {}
            for row in expected:
                namespace = row["namespace"]
                candidates = (
                    f"assets/{namespace}/lang/vi_vn.lang",
                    f"assets/{namespace}/lang/vi_VN.lang",
                    f"assets/{namespace}/lang/vi_vn.json",
                    f"assets/{namespace}/lang/vi_VN.json",
                )
                member = next((name for name in candidates if name in members), None)
                if member is None:
                    untranslated.append((namespace, row["key"], "<missing locale>"))
                    continue
                if member not in cache:
                    text = archive.read(member).decode("utf-8")
                    cache[member] = json.loads(text) if member.endswith(".json") else parse_lang(text)
                actual = cache[member].get(row["key"], "")
                if not actual or actual == row["en"]:
                    untranslated.append((namespace, row["key"], actual))
        self.assertEqual(untranslated, [])

    def test_final_thirteen_runtime_prose_gaps_are_translated_and_packaged(self):
        expected = {
            "immersiveengineering": {
                "modifier.thermalinversion.desc": "§oNóng & Lạnh!§r\\nĐánh kẻ địch ở nơi nóng hoặc lạnh sẽ khiến chúng lạnh cóng hoặc bốc cháy.",
                "key.immersiveengineering.magnetEquip": "Magnetic Shield Glove (nhấn đúp)",
                "key.immersiveengineering.chemthrowerSwitch": "Đổi bình Chemthrower",
                "desc.immersiveengineering.info.attachedTo": "Liên kết từ %1$s, %2$s, %3$s",
                "desc.immersiveengineering.info.attachedToDim": "Liên kết từ %1$s, %2$s, %3$s trong Dimension %4$s",
                "desc.immersiveengineering.info.energyStored": "Đã lưu trữ %1$s Flux",
                "desc.immersiveengineering.info.energyStoredEU": "Đã lưu trữ %1$s EU",
            },
            "enderutilities": {
                "enderutilities.key.togglemode": "Chuyển chế độ",
                "enderutilities.gui.infoarea.drawbridge": "- Kéo dài hoặc thu lại một hàng block|lf- Có thể điều chỉnh chiều dài tối đa của hàng|lf- Có thể điều chỉnh thời gian chờ giữa các thao tác|lf- Để dùng hướng cụ thể của block hoặc giữ nguyên|lf  dữ liệu TileEntity, hãy đặt chúng trong thế giới|lf  rồi nhấn \"Lấy trạng thái block từ thế giới\"|lf- Với Normal Drawbridge, trạng thái được lấy|lf  từ block đầu tiên phía trước Drawbridge|lf- Có thể ngụy trang bằng cách nhấp chuột phải với|lf  tay chính trống trong khi tay phụ đang cầm block|lf- Lén + nhấp chuột phải bằng tay trống|lf  để gỡ lớp ngụy trang",
                "enderutilities.gui.infoarea.inserter_filtered": "- Cố chèn item vào \"đầu ra bên\" trước|lf- Nếu thất bại hoặc bộ lọc không cho phép,|lf  item sẽ đi ra phía \"đầu ra thường\"|lf- Lọc đầu vào chỉ áp dụng khi kéo item; nguồn khác|lf  vẫn có thể đẩy item không được phép vào Inserter|lf- Lén + nhấp chuột phải bằng tay trống để đổi các phía đầu ra|lf- Giới hạn stack quy định số item được chuyển mỗi lần|lf- (Shift và/hoặc Ctrl) nhấp trái/phải/giữa hoặc cuộn trên|lf  các nút +/- để thay đổi giá trị",
                "enderutilities.gui.infoarea.inserter_normal": "- Cố chèn item vào \"đầu ra bên\" trước|lf- Nếu thất bại, item sẽ đi ra phía \"đầu ra thường\"|lf- Lén + nhấp chuột phải bằng tay trống để đổi các phía đầu ra|lf- Giới hạn stack quy định số item được chuyển mỗi lần|lf- (Shift và/hoặc Ctrl) nhấp trái/phải/giữa hoặc cuộn trên|lf  các nút +/- để thay đổi giá trị",
            },
            "bewitchment": {
                "advancements.bewitchment.cauldron.title": "Mắt kỳ giông, chân ếch nhái",
            },
        }
        source_files = {
            "immersiveengineering": ROOT / "work" / "translated" / "tooltips" / "immersiveengineering.json",
            "enderutilities": ROOT / "work" / "translated" / "p2_enderutilities.json",
            "bewitchment": ROOT / "work" / "translated" / "advancements" / "bewitchment.json",
        }
        for namespace, entries in expected.items():
            target = json.loads(source_files[namespace].read_text(encoding="utf-8"))
            for key, value in entries.items():
                self.assertEqual(target.get(key), value, key)

        roots = json.loads(
            (ROOT / "work" / "patchouli_vi" / "assets" / "roots" / "patchouli_books" / "roots_guide" / "vi_vn" / "entries" / "concepts" / "wild_magic.json").read_text(encoding="utf-8")
        )
        self.assertEqual(roots["name"], "Lịch sử Wild Magic")

        with zipfile.ZipFile(self._path) as zf:
            for namespace, entries in expected.items():
                packaged = parse_lang(zf.read(f"assets/{namespace}/lang/vi_vn.lang").decode("utf-8"))
                for key, value in entries.items():
                    self.assertEqual(packaged.get(key), value, key)
            roots = json.loads(
                zf.read("assets/roots/patchouli_books/roots_guide/vi_vn/entries/concepts/wild_magic.json").decode("utf-8")
            )
            self.assertEqual(roots["name"], "Lịch sử Wild Magic")

    def test_reviewed_p2_ui_batch_is_complete_and_packaged(self):
        namespaces = {
            "ftbutilities": 32,
            "ftblib": 20,
            "ftbbackups": 30,
            "jei": 20,
            "jeiutilities": 12,
            "jeresources": 18,
            "enderutilities": 7,
            "actuallyadditions": 25,
            "extrautils2": 13,
        }
        total = 0
        for namespace, expected in namespaces.items():
            source = ROOT / "source" / f"p2_{namespace}.lang"
            translated = ROOT / "work" / "translated" / f"p2_{namespace}.json"
            source_entries = parse_lang(source.read_text(encoding="utf-8"))
            target = json.loads(translated.read_text(encoding="utf-8"))
            self.assertEqual(list(target), list(source_entries), namespace)
            self.assertEqual(len(target), expected, namespace)
            total += expected
        self.assertEqual(total, 177)

    """Build once per suite; all read-only assertions share the immutable ZIP."""

    @classmethod
    def setUpClass(cls):
        cls._td = tempfile.TemporaryDirectory()
        cls._path = Path(cls._td.name) / "test.zip"
        # stage= must stay inside the temp dir: the default points into the
        # real build/, so every suite run seeded a .partial- tree there.
        build_pack.build(output=cls._path, stage=Path(cls._td.name) / "stage")

    @classmethod
    def tearDownClass(cls):
        cls._td.cleanup()

    def build_zip(self):
        # Return a no-op cleanup handle for backwards-compatible test bodies.
        class Shared:
            @staticmethod
            def cleanup():
                return None

        return Shared(), self._path

    def test_client_bundle_contains_triumph_overlay(self):
        import importlib.util
        import tempfile
        bundle_spec = importlib.util.spec_from_file_location("build_client_bundle_test", ROOT / "tools" / "build_client_bundle.py")
        bundle = importlib.util.module_from_spec(bundle_spec)
        bundle_spec.loader.exec_module(bundle)
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "client.zip"
            entries = bundle.build(output)
            expected = {
                f"config/triumph/script/triumph/dj2/{path.name}"
                for path in (ROOT / "work" / "client_overlay_vi" / "config" / "triumph" / "script" / "triumph" / "dj2").glob("*.txt")
            }
            self.assertEqual(len(expected), 27)
            self.assertTrue(expected.issubset(entries))
            with zipfile.ZipFile(output) as zf:
                self.assertTrue(expected.issubset(zf.namelist()))

    def test_triumph_overlay_preserves_scripts_and_translates_literals(self):
        source_dir = ROOT.parent / "_upstream" / "Divine-Journey-2" / "overrides" / "config" / "triumph" / "script" / "triumph" / "dj2"
        overlay_dir = ROOT / "work" / "client_overlay_vi" / "config" / "triumph" / "script" / "triumph" / "dj2"
        source_files = sorted(source_dir.glob("*.txt"))
        overlay_files = sorted(overlay_dir.glob("*.txt"))
        self.assertEqual(len(source_files), 27)
        self.assertEqual([p.name for p in overlay_files], [p.name for p in source_files])

        import re
        literal_re = re.compile(r'(set(?:Title|Description)\(")((?:\\.|[^"\\])*)("\))')
        for source_path, overlay_path in zip(source_files, overlay_files):
            source = source_path.read_text(encoding="utf-8")
            overlay = overlay_path.read_text(encoding="utf-8")
            source_literals = [m.group(2) for m in literal_re.finditer(source)]
            overlay_literals = [m.group(2) for m in literal_re.finditer(overlay)]
            self.assertEqual(len(source_literals), 2, source_path.name)
            self.assertEqual(len(overlay_literals), 2, overlay_path.name)
            self.assertNotEqual(source_literals, overlay_literals, overlay_path.name)
            self.assertEqual(literal_re.sub(r"\1<LITERAL>\3", source), literal_re.sub(r"\1<LITERAL>\3", overlay), overlay_path.name)
            self.assertNotRegex(" ".join(overlay_literals).lower(), r"\b(craft|obtain|unlock|complete|make|find out|progression related)\b")

    def test_runtime_locale_overlays_cover_the_reviewed_ui_manifest(self):
        """Every reviewed runtime UI/prose key must ship in vi_vn only."""
        _, path = self.build_zip()
        source_dir = ROOT / "work" / "runtime_locale_sources"
        translated_dir = ROOT / "work" / "translated" / "runtime_locales"
        expected_namespaces = {
            "enderio", "draconicevolution", "mekanism", "appliedenergistics2",
            "galacticraftcore", "galacticraftplanets", "integrateddynamics",
            "thermalexpansion", "bloodmagic", "bloodmagicguide", "abyssalcraft",
        }
        self.assertEqual({p.stem for p in source_dir.glob("*.lang") if p.stem in expected_namespaces}, expected_namespaces)
        with zipfile.ZipFile(path) as zf:
            for namespace in sorted(expected_namespaces):
                source = parse_lang((source_dir / f"{namespace}.lang").read_text(encoding="utf-8"))
                translated_path = translated_dir / f"{namespace}.json"
                self.assertTrue(translated_path.exists(), f"missing runtime translation: {translated_path}")
                translated = json.loads(translated_path.read_text(encoding="utf-8"))
                self.assertEqual(set(translated), set(source), f"runtime translation coverage mismatch: {namespace}")
                member = locale_member(set(zf.namelist()), namespace)
                self.assertIsNotNone(member, namespace)
                built = parse_lang(zf.read(member).decode("utf-8"))
                self.assertTrue(set(source).issubset(built), f"runtime keys not merged: {namespace}")
                self.assertNotIn(f"assets/{namespace}/lang/en_us.lang", zf.namelist())
                self.assertNotIn(f"assets/{namespace}/lang/en_US.lang", zf.namelist())

    def test_runtime_translation_batches_have_exact_tokens_and_structure(self):
        import importlib.util
        validator_path = ROOT / "tools/validate_runtime_locales.py"
        spec = importlib.util.spec_from_file_location("validate_runtime_locales", validator_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        report, errors = module.validate()
        self.assertEqual(errors, [])

    def test_client_bundle_includes_all_non_resourcepack_localization_overlays(self):
        import importlib.util
        bundle_path = ROOT / "tools/build_client_bundle.py"
        spec = importlib.util.spec_from_file_location("build_client_bundle", bundle_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        entries = module.build()
        self.assertIn("resourcepacks/DJ2_Viet_Hoa_2.23.4.zip", entries)
        self.assertIn("config/tips.cfg", entries)
        self.assertIn("scripts/JEI/Excavator.zs", entries)
        self.assertIn("scripts/ContentTweaker/ContentTweakerItems.zs", entries)
        triumph = [name for name in entries if name.startswith("config/triumph/script/triumph/dj2/")]
        self.assertEqual(len(triumph), 27)
        self.assertTrue(entries)

    def test_translated_locales_pass_the_full_validator(self):
        """Newline semantics, registry names and protected terms, in one gate.

        validate_runtime_locales.py only covers work/runtime_locale_batches; the
        pack is built from work/translated/**, which went unchecked until three
        real bugs (a wrong-meaning tconstruct tooltip, a dropped literal \\n in
        openblocks, a real newline in storagedrawers) shipped through it.
        """
        script = ROOT / "tools" / "validate_translated_locales.py"
        self.assertTrue(script.exists(), "validate_translated_locales.py is missing")
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["errors"], [], f"validator errors: {payload['errors'][:5]}")
        self.assertEqual(proc.returncode, 0)

    def test_translated_locales_preserve_newline_semantics(self):
        """MC 1.12.2 splits .lang tooltips on the literal two-character \\n.

        A real U+000A terminates the entry instead, so everything after it
        vanishes in game while byte-level checks still pass. Dropping a literal
        \\n silently merges two tooltip lines. Both shipped undetected before:
        validate_runtime_locales.py guards work/runtime_locale_batches, not the
        work/translated/* trees that build_pack.py actually reads.
        """
        spec = importlib.util.spec_from_file_location(
            "validate_translated_locales", ROOT / "tools" / "validate_translated_locales.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        report, errors = module.validate()
        self.assertTrue(report, "no translation pairs were checked at all")
        newline_errors = [e for e in errors if "newline" in e or "literal" in e]
        self.assertEqual(newline_errors, [], "newline semantics broken")
        self.assertEqual(errors, [], "translated locales failed validation")

    def test_one_english_label_has_one_vietnamese_rendering(self):
        """Two renderings of one label read as two different features.

        Bucket by the SOURCE string -- grouping by the Vietnamese side finds
        nothing, because the divergent strings are exactly the ones that do not
        match each other. Keys naming a mode, a live status, or one half of an
        on/off pair are listed in CONSISTENCY_EXEMPT with the reason.
        """
        spec = importlib.util.spec_from_file_location(
            "validate_translated_locales", ROOT / "tools" / "validate_translated_locales.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        labels = {
            "Upgrades": [("Nâng cấp", "a:gui.x"), ("Upgrades", "b:gui.y")],
        }
        self.assertTrue(
            module.consistency_errors(labels),
            "an untranslated duplicate label must be reported",
        )
        agreed = {"Upgrades": [("Nâng cấp", "a:gui.x"), ("Nâng cấp", "b:gui.y")]}
        self.assertEqual(module.consistency_errors(agreed), [])
        _, errors = module.validate()
        inconsistent = [e for e in errors if e.startswith("inconsistent term")]
        self.assertEqual(inconsistent, [], f"inconsistent terms: {inconsistent[:5]}")

    def test_multiline_tooltips_stay_within_official_line_widths(self):
        """Self-wrapping prose is not overflow; fixed frames are the risk.

        A source segment wider than any screen (Blood Magic's guide book ships
        4112px) proves that string self-wraps and \\n only marks paragraphs.
        For the fixed-frame remainder the ceiling comes from the mod's own
        official translations, never a number invented here.
        """
        script = ROOT / "tools" / "check_multiline_tooltips.py"
        self.assertTrue(script.exists(), "check_multiline_tooltips.py is missing")
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(proc.stdout)
        self.assertEqual(
            payload["over_reference"], [],
            f"lines wider than the mod's own official translations: "
            f"{payload['over_reference'][:5]}",
        )
        self.assertTrue(payload["rows"], "no multi-line tooltips were measured")
        self.assertEqual(proc.returncode, 0)

    def test_edge_spaces_match_the_source_exactly(self):
        """MC concatenates .lang values, so edge spaces are load-bearing.

        An added leading space shifts a GUI label out of alignment; a dropped
        trailing space glues the next fragment onto the last word. 35 shipped
        strings carried one (bloodmagicguide alone had 14) before this gate.
        """
        spec = importlib.util.spec_from_file_location(
            "validate_translated_locales", ROOT / "tools" / "validate_translated_locales.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _, errors = module.validate()
        space_errors = [e for e in errors if "space" in e]
        self.assertEqual(space_errors, [], f"edge space drift: {space_errors[:5]}")

    def test_numbers_survive_translation_unchanged(self):
        """A number that changes value in translation is a factual bug.

        Digits written as words ("one" -> "1", "2nd" -> "thứ hai") are fine, so
        this compares the multiset of numerals and tolerates the wording swap;
        what it will not tolerate is 8,000 becoming 8.000 (a 1000x misread for
        anyone reading English-style separators, which is what the game's own
        runtime numbers use).
        """
        pairs, mismatched = 0, []
        numeral = re.compile(r"(?<![\w%$])(\d+(?:[.,]\d+)?)")
        codes = re.compile(r"§.|&[0-9a-fk-orA-FK-OR]")
        for source_dir, target_dir in (
            ("work/runtime_locale_sources", "work/translated/runtime_locales"),
            ("source/tooltips", "work/translated/tooltips"),
        ):
            for lang_path in sorted((ROOT / source_dir).glob("*.lang")):
                json_path = ROOT / target_dir / f"{lang_path.stem}.json"
                if not json_path.exists():
                    # Every source file here is translated. A missing store means the
                    # store was lost, not that this file is exempt -- skipping would
                    # quietly drop it from the check.
                    self.fail(f"missing translation store: {json_path.relative_to(ROOT)}")
                source = {}
                for line in lang_path.read_text(encoding="utf-8").splitlines():
                    if "=" not in line or line.lstrip().startswith("#"):
                        continue
                    key, value = line.split("=", 1)
                    source.setdefault(key.strip(), value.strip())
                target = json.loads(json_path.read_text(encoding="utf-8"))
                for key, english in source.items():
                    vietnamese = target.get(key)
                    if not isinstance(vietnamese, str):
                        continue
                    pairs += 1
                    english_numbers = numeral.findall(codes.sub("", english))
                    if not english_numbers:
                        continue
                    translated = numeral.findall(codes.sub("", vietnamese))
                    # Only separator-style drift is a defect here; a numeral the
                    # translation spells out in words is expected to disappear.
                    for number in english_numbers:
                        if "," not in number and "." not in number:
                            continue
                        swapped = number.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
                        if number in translated or swapped not in translated:
                            continue
                        # Vietnamese swaps both separators: 50,000 -> 50.000 and
                        # 1.5 -> 1,5 are the correct local spellings, not the
                        # 1000x misreads this guard exists to catch. Compare the
                        # VALUE both ways and only report a real magnitude change.
                        def value(text, thousands, decimal):
                            return text.replace(thousands, "").replace(decimal, ".")

                        english_value = value(number, ",", ".")
                        localized_value = value(swapped, ".", ",")
                        if english_value != localized_value:
                            mismatched.append(f"{lang_path.stem}:{key} {number} -> {swapped}")
        self.assertTrue(pairs, "no pairs were compared at all")
        self.assertEqual(
            mismatched, [], f"decimal/thousands separator changed: {mismatched[:5]}"
        )

    def test_brackets_close_and_keep_their_figures(self):
        """Brackets carry specs; a dropped digit silently rewrites one.

        Counting brackets is the wrong check -- emoticons (`=)`, `:(`, `:[`)
        leave four sources unbalanced on purpose, and 42 strings legitimately
        drop a bracket because the Vietnamese rephrases the clause. What is
        never acceptable: a bracket that fails to close, or a number inside a
        source bracket that vanishes (e.g. "(25 blocks)" losing the 25).
        """
        spec = importlib.util.spec_from_file_location(
            "validate_translated_locales", ROOT / "tools" / "validate_translated_locales.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(module.unbalanced("(a", "(", ")"), "never-closed bracket missed")
        self.assertTrue(module.unbalanced("a)b(", "(", ")"), "closed-before-open missed")
        self.assertFalse(module.unbalanced("(a) (b)", "(", ")"))
        _, errors = module.validate()
        bracket_errors = [
            e for e in errors if e.startswith("unbalanced") or "figure dropped" in e
        ]
        self.assertEqual(bracket_errors, [], f"bracket damage: {bracket_errors[:5]}")

    def test_vietnamese_common_nouns_are_not_title_cased_mid_sentence(self):
        """English capitalises item names mid-sentence; Vietnamese does not.

        Vanilla nouns leaked their English casing into prose -- "3 chai Nước",
        "4 quyển Sách", "Xẻng Đá" -- 36 times against 555 correct lowercase
        uses of the very same words, so the pack's own majority settles it.
        Proper nouns kept in English (Blood Altar, Variable Card) and Title
        Case GUI labels are excluded: only running prose is checked.
        """
        vietnamese_diacritic = re.compile(
            r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]",
            re.I,
        )
        codes = re.compile(r"§.|&[0-9a-fk-orA-FK-OR]")
        common_nouns = [
            "Xương", "Gậy", "Xô", "Sách", "Nước", "Mũi tên",
            "Đất", "Đá", "Trứng", "Sắt", "Bột", "Da", "Hạt",
        ]
        offenders = []
        for source_dir, target_dir in (
            ("work/runtime_locale_sources", "work/translated/runtime_locales"),
            ("source/tooltips", "work/translated/tooltips"),
        ):
            for lang_path in sorted((ROOT / source_dir).glob("*.lang")):
                json_path = ROOT / target_dir / f"{lang_path.stem}.json"
                if not json_path.exists():
                    # Every source file here is translated. A missing store means the
                    # store was lost, not that this file is exempt -- skipping would
                    # quietly drop it from the check.
                    self.fail(f"missing translation store: {json_path.relative_to(ROOT)}")
                source = {}
                for line in lang_path.read_text(encoding="utf-8").splitlines():
                    if "=" not in line or line.lstrip().startswith("#"):
                        continue
                    key, value = line.split("=", 1)
                    source.setdefault(key.strip(), value.strip())
                target = json.loads(json_path.read_text(encoding="utf-8"))
                for key, english in source.items():
                    vietnamese = target.get(key)
                    if not isinstance(vietnamese, str):
                        continue
                    plain_en = codes.sub("", english)
                    plain_vi = codes.sub("", vietnamese)
                    words = re.findall(r"[A-Za-z']+", plain_en)
                    if not words:
                        continue
                    title_ratio = sum(1 for w in words if w[:1].isupper()) / len(words)
                    # A Title Case label is not a sentence; skip those. Trailing
                    # sentence punctuation does not change that: achievement
                    # NAMES like "Bookworm!" / "A Dark Land of Riches!" are
                    # titles that happen to end in "!", and their Title Case
                    # Vietnamese ("Mot Sach!") is deliberate. Only interior
                    # punctuation marks real prose.
                    if title_ratio >= 0.6 and not re.search(
                        r"[.!?]", re.sub(r"[.!?]+$", "", plain_vi)
                    ):
                        continue
                    for noun in common_nouns:
                        pattern = r"(?<=[a-zà-ỹ,]\s)" + re.escape(noun) + r"(?![\wÀ-ỹ])"
                        if re.search(pattern, plain_vi):
                            offenders.append(f"{lang_path.stem}:{key} {noun!r}")
        self.assertEqual(
            offenders, [], f"English casing leaked into prose: {offenders[:5]}"
        )

    def test_split_key_families_agree_within_a_button_set(self):
        """A sentence cut across keys must still read as one sentence.

        The XP Obelisk ships six sibling buttons; five said "Cất/Rút ... của
        người chơi" and `store.all` alone said "Lưu ... Người Chơi", which the
        player sees stacked in one GUI. Only sibling keys under one base are
        compared, because that is the set rendered together.
        """
        codes = re.compile(r"§.|&[0-9a-fk-orA-FK-OR]")
        target = ROOT / "work/translated/runtime_locales/enderio.json"
        strings = json.loads(target.read_text(encoding="utf-8"))
        joined = {}
        for action in ("store", "retrieve"):
            for amount in ("1", "10", "all"):
                base = f"enderio.gui.xp_obelisk.button.{action}.{amount}.line"
                parts = [
                    codes.sub("", strings[f"{base}{n}"]).strip()
                    for n in (1, 2)
                    if f"{base}{n}" in strings
                ]
                if parts:
                    joined[f"{action}.{amount}"] = " ".join(parts)
        self.assertTrue(joined, "XP obelisk button family not found")
        for action, verb in (("store", "Cất"), ("retrieve", "Rút")):
            verbs = {
                text.split()[0]
                for name, text in joined.items()
                if name.startswith(action) and text
            }
            self.assertEqual(
                verbs, {verb}, f"{action} buttons disagree on the verb: {verbs}"
            )
        capitalised = [n for n, t in joined.items() if "Người Chơi" in t]
        self.assertEqual(
            capitalised, [], f"'người chơi' title-cased mid-label: {capitalised}"
        )

    def test_no_accidental_word_doubling(self):
        """"đã cho cho" is a typo; "từ từ" is a word. Only flag the first.

        Vietnamese reduplication (từ từ, dần dần, chuồn chuồn) and onomatopoeia
        (pằng pằng, chít chít) repeat a syllable legitimately -- 21 of 49 hits.
        Real defects found this way: "đã cho cho operator" (x3) and "Ánh sáng
        sáng thế" (a word boundary swallowed by the neighbouring word).
        """
        codes = re.compile(r"§.|&[0-9a-fk-orA-FK-OR]")
        # Confirmed reduplication/onomatopoeia; anything else must be reviewed.
        reduplicated = {
            "từ", "dần", "ngày", "đêm", "lần", "luôn", "mãi", "rào", "chuồn",
            "pằng", "chít", "tanh", "vèo", "măm", "ầm", "hô", "nào", "sai",
            "sao", "ngon", "xẹt", "thao", "khụ", "đâm", "chọc", "bị", "có",
            "tại", "bộ", "chăng", "xa", "nho", "hây", "đau", "vừa", "càng",
            # Machine/electrical hum and "song song" (parallel), all checked in
            # context: "cỗ máy kêu vo vo", "Điện chạy rè rè", "Khiên phép kêu
            # vù vù", "đặt song song với mặt khối".
            "vo", "rè", "vù", "song",
            # Animal-cry onomatopoeia from the sound-subtitle batch. Vietnamese
            # spells these as reduplicatives, so the doubling IS the word:
            # "Sheepuff kêu be be", "Lava Cat kêu meo meo", "Endermini kêu chíp
            # chíp", "Frog kêu ộp ộp", "Lava Cat kêu gừ gừ", "Lava Cat xèo xèo",
            # "Endermini nhìn chằm chằm".
            "be", "meo", "chíp", "ộp", "gừ", "xèo", "chằm",
            # Compound boundaries where the second word starts a NEW compound,
            # verified in context once the English sources were restored:
            #   "tinh chất | chất lỏng"  (essence | liquid)
            #   "cây cầu | cầu vồng"     (bridge | rainbow)
            #   "hỗn hợp | hợp kim"      (mixture | alloy)
            #   "hay không | không quan trọng" (whether or not | does not matter)
            "chất", "cầu", "hợp", "không",
            # Reduplication used as deliberate flavour text in Botania's
            # lexicon: "Bắn bắn bắn bắn", "Xinh xinh, sáng sáng", "Bạn xoay
            # tôi vòng vòng", and "vân vân" (= etc.).
            "bắn", "xinh", "sáng", "vòng", "vân",
        }
        offenders = []
        for source_dir, target_dir in (
            ("work/runtime_locale_sources", "work/translated/runtime_locales"),
            ("source/tooltips", "work/translated/tooltips"),
        ):
            for lang_path in sorted((ROOT / source_dir).glob("*.lang")):
                json_path = ROOT / target_dir / f"{lang_path.stem}.json"
                if not json_path.exists():
                    # Every source file here is translated. A missing store means the
                    # store was lost, not that this file is exempt -- skipping would
                    # quietly drop it from the check.
                    self.fail(f"missing translation store: {json_path.relative_to(ROOT)}")
                source = {}
                for line in lang_path.read_text(encoding="utf-8").splitlines():
                    if "=" not in line or line.lstrip().startswith("#"):
                        continue
                    key, value = line.split("=", 1)
                    source.setdefault(key.strip(), value.strip())
                target = json.loads(json_path.read_text(encoding="utf-8"))
                for key, english in source.items():
                    vietnamese = target.get(key)
                    if not isinstance(vietnamese, str):
                        continue
                    plain_en = codes.sub("", english)
                    plain_vi = codes.sub("", vietnamese)
                    for match in re.finditer(
                        r"\b([\wÀ-ỹ]{2,})(\s+)\1\b", plain_vi, re.I | re.U
                    ):
                        word = match.group(1)
                        if word.lower() in reduplicated:
                            continue
                        # The source repeating it makes the repeat intentional.
                        if re.search(
                            r"\b" + re.escape(word) + r"\s+" + re.escape(word) + r"\b",
                            plain_en,
                            re.I,
                        ):
                            continue
                        offenders.append(f"{lang_path.stem}:{key} {word!r}")
        self.assertEqual(offenders, [], f"doubled words: {offenders[:5]}")

    def test_translations_stay_inside_the_renderable_character_set(self):
        """The pack font decides what a player actually sees.

        Emoji sit outside the BMP and the 1.12.2 unicode pages stop at
        U+FFFF, so one would render as a blank box. A stray CJK glyph is
        different: the font *can* draw it, but it only ever arrives as
        machine-translation debris welded onto a Vietnamese word, which is
        why this asserts on the corpus rather than trusting the font.
        """
        offenders = []
        for source_dir, translated_dir in (
            ("work/runtime_locale_sources", "work/translated/runtime_locales"),
            ("source/tooltips", "work/translated/tooltips"),
        ):
            translated_root = ROOT / translated_dir
            if not translated_root.is_dir():
                continue
            for path in sorted(translated_root.glob("*.json")):
                source_path = ROOT / source_dir / path.name
                source = (
                    json.loads(source_path.read_text(encoding="utf-8"))
                    if source_path.is_file()
                    else {}
                )
                for key, value in json.loads(
                    path.read_text(encoding="utf-8")
                ).items():
                    if not isinstance(value, str):
                        continue
                    english = source.get(key, "")
                    for char in value:
                        if char in english:
                            continue
                        point = ord(char)
                        if point > 0xFFFF or (
                            0x3040 <= point <= 0x30FF
                            or 0x3400 <= point <= 0x9FFF
                            or 0xAC00 <= point <= 0xD7AF
                        ):
                            offenders.append(f"{path.name}:{key}: {char!r}")
        self.assertEqual(offenders, [], f"unrenderable characters: {offenders}")

    def test_second_person_pronoun_matches_each_mods_voice(self):
        """Mixing "bạn" and "ngươi" inside one string is always wrong.

        Across mods the split is deliberate: EvilCraft's villain voice says
        "ngươi", the Blood Magic journal says "bạn", and the Valkyrie Queen
        dialogue is 10/10 "ngươi". So this cannot assert a single pack-wide
        pronoun -- it asserts that no single string uses both, and that
        plain UI keys (tooltips, config, commands) never use "ngươi".
        """
        neutral = re.compile(
            r"(?<![\w\u00C0-\u1EF9])[Bb]ạn(?![\w\u00C0-\u1EF9])(?!\s*(?:bè|thân))"
        )
        archaic = re.compile(r"(?<![\w\u00C0-\u1EF9])[Nn]gươi(?![\w\u00C0-\u1EF9])")
        plain_ui = re.compile(
            r"^(tooltip\.|config\.|command|option\.|jei\.)", re.IGNORECASE
        )
        mixed, archaic_ui = [], []
        for _, translated_dir in (
            ("work/runtime_locale_sources", "work/translated/runtime_locales"),
            ("source/tooltips", "work/translated/tooltips"),
        ):
            root = ROOT / translated_dir
            if not root.is_dir():
                continue
            for path in sorted(root.glob("*.json")):
                for key, value in json.loads(
                    path.read_text(encoding="utf-8")
                ).items():
                    if not isinstance(value, str):
                        continue
                    plain = re.sub(r"§.|&[0-9a-fk-orA-FK-OR]", "", value)
                    if neutral.search(plain) and archaic.search(plain):
                        mixed.append(f"{path.stem}:{key}")
                    if archaic.search(plain) and plain_ui.search(key):
                        archaic_ui.append(f"{path.stem}:{key}")
        self.assertEqual(mixed, [], f"both pronouns in one string: {mixed}")
        self.assertEqual(archaic_ui, [], f"'ngươi' in plain UI: {archaic_ui}")

    def test_lang_parser_keeps_the_spaces_that_glue_strings_together(self):
        """The parser must not strip values, or one whole check goes blind.

        MC concatenates lang values, so ``"Health: "`` + 20 needs its trailing
        space and a translation that drops it renders ``Máu:20``. The leading/
        trailing-space check compares source against translation -- but it read
        the source through a parser that called ``.strip()``, so both sides
        arrived space-less and the check could never fire. It silently passed
        11 real defects. Pin the parser, not just the check.
        """
        module = importlib.util.module_from_spec(
            (
                spec := importlib.util.spec_from_file_location(
                    "validate_translated_locales_parser",
                    ROOT / "tools" / "validate_translated_locales.py",
                )
            )
        )
        spec.loader.exec_module(module)
        parsed = module.parse_lang(
            "a=  padded both sides  \n"
            "b=trailing only \n"
            "c= leading only\n"
            "# comment=ignored\n"
        )
        self.assertEqual(parsed["a"], "  padded both sides  ")
        self.assertEqual(parsed["b"], "trailing only ")
        self.assertEqual(parsed["c"], " leading only")
        self.assertNotIn("# comment", parsed)

    def test_every_shipped_namespace_is_one_a_mod_actually_registers(self):
        """A key emitted under the wrong namespace is invisible, not wrong-looking.

        `books_bloodmagic` shipped 274 guide entries under `bloodmagic`, but the
        JAR registers every one of them under `bloodmagicguide`. The dead copy
        rendered nowhere, drifted 36 keys away from the live copy, and no
        string-level check could see it: both copies were valid Vietnamese.
        """
        import zipfile

        with zipfile.ZipFile(self._path) as zf:
            shipped = {
                name.split("/")[1]
                for name in zf.namelist()
                if name.startswith("assets/") and name.endswith(".lang")
            }
            guide_owners = set()
            for name in zf.namelist():
                if not name.endswith(".lang"):
                    continue
                text = zf.read(name).decode("utf-8")
                if "guide.bloodmagic.entry." in text:
                    guide_owners.add(name.split("/")[1])

        self.assertIn("bloodmagicguide", shipped)
        self.assertEqual(
            guide_owners,
            {"bloodmagicguide"},
            "guide.bloodmagic.* must ship under exactly one namespace",
        )

    def test_no_translation_carries_a_raw_tab(self):
        """MC 1.12's bitmap font has no U+0009 glyph; sources spell it `\\t`."""
        import zipfile

        offenders = []
        with zipfile.ZipFile(self._path) as zf:
            for name in zf.namelist():
                if not name.endswith(".lang"):
                    continue
                for line in zf.read(name).decode("utf-8").splitlines():
                    if "=" in line and "\t" in line.split("=", 1)[1]:
                        offenders.append(f"{name}:{line.split('=', 1)[0]}")
        self.assertEqual(offenders[:5], [], f"{len(offenders)} values contain a real tab")

    def test_tinker_stat_labels_are_all_present_in_the_source(self):
        """The book's stat labels come from `stat.*`, not from the book JSON.

        Four in-game screenshots showed Tinker material pages with Vietnamese
        trait tooltips sitting next to English `Head` / `Durability` /
        `Mining Level` labels. The cause was not a bad translation: 29 of the
        JAR's 44 `stat.*` keys had never been copied into
        `work/runtime_locale_sources/tconstruct.lang`, so nothing ever asked
        for them. A key absent from the source is invisible to every checker
        that compares source against translation.

        Three labels stay English on purpose -- `Arrow Shaft`, `Fletching` and
        `Bowstring` are also real JEI item names (`item.tconstruct.*.name`),
        and PROTECTED_TERM correctly refuses to translate them.
        """
        import zipfile

        instance = Path(
            "C:/Users/Administrator/AppData/Roaming/ElyPrismLauncher"
            "/instances/Divine Journey 2/minecraft"
        )
        jar = next(
            p
            for p in (instance / "mods").glob("*.jar")
            if p.name.startswith("TConstruct-")
        )
        with zipfile.ZipFile(jar) as zf:
            name = next(
                n
                for n in zf.namelist()
                if n.lower().endswith("en_us.lang") and "/lang/" in n
            )
            english = parse_lang(zf.read(name).decode("utf-8", errors="replace"))

        source = parse_lang(
            (ROOT / "work" / "runtime_locale_sources" / "tconstruct.lang").read_text(
                encoding="utf-8"
            )
        )
        missing = sorted(k for k in english if k.startswith("stat.") and k not in source)
        self.assertEqual(missing, [], f"{len(missing)} stat.* labels never reach translation")

        keep_english = {"stat.shaft.name", "stat.fletching.name", "stat.bowstring.name"}
        with zipfile.ZipFile(self._path) as zf:
            shipped = parse_lang(
                zf.read("assets/tconstruct/lang/vi_vn.lang").decode("utf-8")
            )
        untranslated = sorted(
            key
            for key, value in shipped.items()
            if key.startswith("stat.")
            and key.endswith(".name")
            and key not in keep_english
            and value == english.get(key)
        )
        self.assertEqual(untranslated, [], "stat.* labels still shipping in English")

    def test_no_shipped_key_carries_two_different_translations(self):
        """One key, one meaning -- unless two mods genuinely disagree in English.

        `books_bloodmagic` shipped 274 keys a second time under a namespace no
        JAR registers, and the two copies silently drifted 36 keys apart. No
        string-level check could see it: both copies were valid Vietnamese.
        The only survivors are keys whose *English* differs per mod, so each
        exception here is pinned to the English it translates.
        """
        import zipfile

        # ns -> key -> value, so a key repeated across namespaces is visible.
        by_key = {}
        with zipfile.ZipFile(self._path) as zf:
            for name in zf.namelist():
                if not name.endswith(".lang"):
                    continue
                namespace = name.split("/")[1]
                for line in zf.read(name).decode("utf-8").splitlines():
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    by_key.setdefault(key, {}).setdefault(namespace, value)

        # Distinct English per mod: DivineRPG "Efficiency: %s" vs Mekanism
        # "Efficiency"; FTBLib "Active" vs Mekanism "Water-Cooled". Quark
        # renames vanilla Resistance to "Fortitude", so its potion strings
        # legitimately differ from CoFH's for the same key.
        allowed = {
            "tooltip.efficiency",
            "gui.active",
            "lingering_potion.effect.resistance",
            "splash_potion.effect.resistance",
            # DivineRPG "%1$s walked on spikes" vs ExtraUtilities2
            # "%1$s walked on x pointy spike (ouchies)" -- different
            # English sentences that happen to share a key name.
            "death.attack.spike",
        }
        conflicts = sorted(
            key
            for key, per_ns in by_key.items()
            if len(set(per_ns.values())) > 1 and key not in allowed
        )
        self.assertEqual(
            conflicts[:5],
            [],
            f"{len(conflicts)} keys ship two different translations",
        )

    def test_edge_spaces_are_counted_not_just_detected(self):
        """A has/hasn't check misses indentation depth.

        Two leading spaces mean "sub-item" in a tooltip and one means an
        ordinary continuation line, so ``"  ... and %s more"`` translated with
        a single leading space shipped a mis-indented row that a boolean
        check called equal. Both validators count the spaces now.
        """
        module = importlib.util.module_from_spec(
            (
                spec := importlib.util.spec_from_file_location(
                    "validate_translated_locales_edges",
                    ROOT / "tools" / "validate_translated_locales.py",
                )
            )
        )
        spec.loader.exec_module(module)
        _, errors = module.validate()
        self.assertEqual(
            [e for e in errors if "space" in e],
            [],
            "edge-space drift is live in work/translated",
        )

    def test_quest_lang_validator_also_guards_edge_spaces(self):
        """validate_lang.py covers 8,961 keys the other validator never sees.

        PAIRS in validate_translated_locales.py reaches only 52% of the keys
        that ship; betterquesting, crafttweaker and the enchantment
        descriptions go through validate_lang.py, which had no edge-space
        check at all until an enchantment desc shipped with one dropped.
        """
        spec = importlib.util.spec_from_file_location(
            "validate_lang_edges", ROOT / "tools" / "validate_lang.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        errors = module.validate(
            {"a": "Health: ", "b": "  indented", "c": "plain"},
            {"a": "Máu:", "b": " indented", "c": "plain"},
            protected=(),
        )
        codes = sorted(e.code for e in errors)
        self.assertEqual(codes, ["LEADING_SPACE", "TRAILING_SPACE"])

    def test_no_translation_is_left_empty_or_pointing_at_a_key(self):
        """Two failures that erase a label instead of mistranslating it.

        A value that is itself a lang key renders as raw gibberish in-game.
        TConstruct ships three of those upstream, so the source is compared
        first -- the pack rule is never to fix beyond the source. An empty
        value blanks the label, but ThermalExpansion ships two empty spacer
        rows on purpose, so empty is only an error when the source is not.
        """
        looks_like_key = re.compile(r"[a-z0-9_]+(\.[a-zA-Z0-9_]+){2,}")
        offenders = []
        for source_dir, translated_dir in (
            ("work/runtime_locale_sources", "work/translated/runtime_locales"),
            ("source/tooltips", "work/translated/tooltips"),
        ):
            root = ROOT / translated_dir
            if not root.is_dir():
                continue
            for path in sorted(root.glob("*.json")):
                source = {}
                lang_path = ROOT / source_dir / f"{path.stem}.lang"
                json_path = ROOT / source_dir / f"{path.stem}.json"
                if lang_path.is_file():
                    for line in lang_path.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            name, _, text = line.partition("=")
                            source[name.strip()] = text
                elif json_path.is_file():
                    source = json.loads(json_path.read_text(encoding="utf-8"))
                for key, value in json.loads(
                    path.read_text(encoding="utf-8")
                ).items():
                    if not isinstance(value, str):
                        continue
                    english = source.get(key, "")
                    stripped = value.strip()
                    if (
                        looks_like_key.fullmatch(stripped)
                        and stripped != english.strip()
                    ):
                        offenders.append(f"{path.stem}:{key} -> {stripped}")
                    if not stripped and english.strip():
                        offenders.append(f"{path.stem}:{key} -> empty")
        self.assertEqual(offenders, [], f"erased translations: {offenders}")

    def test_runtime_locale_manifests_do_not_translate_registry_names(self):
        forbidden_prefixes = (
            "item.", "tile.", "block.", "fluid.", "entity.", "material.",
            "oredict.", "ore.", "biome.", "dimension.", "enchantment.",
            "potion.", "itemGroup.",
        )
        for source_path in sorted((ROOT / "work" / "runtime_locale_sources").glob("*.lang")):
            source = parse_lang(source_path.read_text(encoding="utf-8"))
            target_path = ROOT / "work" / "translated" / "runtime_locales" / f"{source_path.stem}.json"
            target = json.loads(target_path.read_text(encoding="utf-8"))
            offenders = [
                key for key, english in source.items()
                if key.startswith(forbidden_prefixes)
                # Tooltip/description keys contain prose; they are not the
                # registry/catalog display name despite sharing its prefix.
                # ".desc.gui", ".tooltip.line1" and ".chat.privateBlock" are
                # prose too, so match the marker as a key SEGMENT rather than
                # only as a suffix.
                and not any(
                    part
                    in ("tooltip", "tooltips", "desc", "description", "chat")
                    for part in key.casefold().split(".")
                )
                and target.get(key) != english
            ]
            self.assertEqual(offenders, [], f"registry/catalog names translated in {source_path.name}")

    def test_server_pack_player_facing_literals_are_localized_without_changing_names(self):
        server = ROOT.parent / "Divine_Journey_2.23.4_Server_Pack"
        content = (server / "scripts/ContentTweaker/ContentTweakerItems.zs").read_text(encoding="utf-8-sig")
        excavator = (server / "scripts/JEI/Excavator.zs").read_text(encoding="utf-8-sig")
        self.assertNotIn("You must be in the Overworld to perform this craft!", content)
        self.assertIn("Bạn phải ở Overworld để thực hiện công thức này!", content)
        self.assertNotIn('var locations = "Generates in the ";', excavator)
        self.assertNotIn('locations ~ " and "', excavator)
        self.assertIn('var locations = "Sinh ra ở ";', excavator)
        self.assertIn('~ " và " ~',excavator)

    def test_advancement_literal_overlays_preserve_logic_and_translate_prose(self):
        inventory = json.loads((ROOT / "work/audit/advancement_literal_inventory.json").read_text(encoding="utf-8"))
        self.assertEqual(len(inventory), 2)
        with zipfile.ZipFile(self._path) as zf:
            for item in inventory:
                source = json.loads((ROOT / "source/advancement_literals" / item["source_file"]).read_text(encoding="utf-8"))
                built = json.loads(zf.read(item["path"]))
                source_copy = json.loads(json.dumps(source))
                built_copy = json.loads(json.dumps(built))
                for data in (source_copy, built_copy):
                    data["display"].pop("title", None)
                    data["display"].pop("description", None)
                self.assertEqual(source_copy, built_copy, item["path"])
                display_text = json.dumps(built["display"], ensure_ascii=False)
                self.assertRegex(display_text, r"[ăâđêôơưàáảãạèéẻẽẹìíỉĩịòóỏõọùúủũụỳýỷỹỵ]", item["path"])

    def test_no_known_english_prose_residue(self):
        known = {
            "dj2.ayeraco_wing.desc2",
            "dj2.chairwand.desc0",
            "dj2.rune_orb.desc0",
            "dj2.dread_plagued_key.desc1",
            "dj2.quest.db.837.desc",
            "dj2.quest.db.857.desc",
            "dj2.quest.db.859.desc",
            "dj2.quest.db.965.desc",
            "dj2.quest.db.968.desc",
            "dj2.quest.db.1008.desc",
            "dj2.quest.db.1103.desc",
            "dj2.quest.db.1148.desc",
            "dj2.quest.db.1731.desc",
            "dj2.quest.db.1441.desc",
            "dj2.quest.db.1643.desc",
            "dj2.quest.db.265.desc",
            "dj2.quest.db.284.desc",
            "dj2.quest.db.218.desc",
            "dj2.quest.ql.20.desc",
            "dj2.quest.db.636.desc",
        }
        td, path = self.build_zip()
        try:
            found = {}
            with zipfile.ZipFile(path) as zf:
                for name in (
                    "assets/crafttweaker/lang/vi_vn.lang",
                    "assets/betterquesting/lang/vi_vn.lang",
                ):
                    values = parse_lang(zf.read(name).decode("utf-8"))
                    found.update({key: values[key] for key in known if key in values})
            self.assertEqual(set(found), known)
            english_markers = (
                "right click", "chance to drop", "smelt your", "harvest some",
                "use some", "craft a", "obtain some", "place it next",
                "slay some", "upgrade your", "prevents endermen", "combine dirty",
                "blast off", "spawn in any non-void", "no need for jars",
            )
            remaining = {
                key: value for key, value in found.items()
                if any(marker in value.lower() for marker in english_markers)
            }
            self.assertFalse(remaining, remaining)
        finally:
            td.cleanup()

    def test_pack_declares_selectable_vietnamese_locale(self):
        td, path = self.build_zip()
        try:
            with zipfile.ZipFile(path) as zf:
                meta = json.loads(zf.read("pack.mcmeta"))
            self.assertEqual(meta["language"]["vi_vn"]["name"], "Tiếng Việt")
            self.assertEqual(meta["language"]["vi_vn"]["region"], "Việt Nam")
            self.assertFalse(meta["language"]["vi_vn"]["bidirectional"])
        finally:
            td.cleanup()

    def test_betterquesting_keeps_exact_source_casing_and_vi_locale(self):
        td, path = self.build_zip()
        try:
            with zipfile.ZipFile(path) as zf:
                names = set(zf.namelist())
            self.assertIn("assets/betterquesting/lang/en_US.lang", names)
            self.assertIn("assets/betterquesting/lang/vi_vn.lang", names)
            self.assertNotIn("assets/betterquesting/lang/en_us.lang", names)
        finally:
            td.cleanup()

    def test_custom_enchantment_descriptions_are_in_owning_namespaces(self):
        td, path = self.build_zip()
        try:
            with zipfile.ZipFile(path) as zf:
                names = set(zf.namelist())
                all_text = "\n".join(
                    zf.read(name).decode("utf-8")
                    for name in names
                    if name.endswith(".lang")
                )
            self.assertNotIn("assets/enchantment_descriptions/", "\n".join(names))
            self.assertNotIn("assets/enchdesc/", "\n".join(names))
            self.assertIn("assets/bibliocraft/lang/vi_vn.lang", names)
            self.assertIn("enchantment.bibliocraft.bibliocraft.readingench.desc=", all_text)
            self.assertIn("assets/enderio/lang/vi_vn.lang", names)
            self.assertIn("enchantment.enderio.soulbound.desc=", all_text)
            self.assertNotIn("enchantment.endercore.soulbound.desc=", all_text)
        finally:
            td.cleanup()

    def test_all_lang_specs_publish_vietnamese_and_exact_english_fallback(self):
        td, path = self.build_zip()
        try:
            with zipfile.ZipFile(path) as zf:
                names = set(zf.namelist())
            expected = {
                "betterquesting": "en_US",
                "bqtweaker": "en_us",
                "crafttweaker": "en_us",
                "divine_journey_2": "en_us",
            }
            for namespace, english_locale in expected.items():
                self.assertIn(f"assets/{namespace}/lang/{english_locale}.lang", names)
                self.assertIn(f"assets/{namespace}/lang/vi_vn.lang", names)
        finally:
            td.cleanup()

    def test_ftbutilities_tpa_messages_are_localized_with_exact_placeholders(self):
        """Join hint advertises /tpa, so every player-facing TPA message must be Vietnamese."""
        td, path = self.build_zip()
        try:
            with zipfile.ZipFile(path) as zf:
                ftbu = parse_lang(zf.read("assets/ftbutilities/lang/vi_vn.lang").decode("utf-8"))
                ftblib = parse_lang(zf.read("assets/ftblib/lang/vi_vn.lang").decode("utf-8"))
            expected = {
                "ftbutilities.lang.tpa.from_to": "%s → %s",
                "ftbutilities.lang.tpa.request_received": "%s muốn dịch chuyển đến chỗ bạn! %s để chấp nhận.",
                "ftbutilities.lang.tpa.request_sent": "Đã gửi yêu cầu dịch chuyển!",
                "ftbutilities.lang.tpa.no_request": "%s không gửi yêu cầu dịch chuyển đến bạn!",
                "ftbutilities.lang.tpa.cant_request": "Không thể gửi yêu cầu dịch chuyển!",
                "ftbutilities.lang.tpa.request_expired": "Yêu cầu dịch chuyển đã hết hạn!",
                "ftbutilities.lang.tpa.request_accepted": "Đã chấp nhận yêu cầu dịch chuyển!",
                "commands.tpa.usage": "/tpa <người_chơi>",
                "commands.tpaccept.usage": "/tpaccept <người_chơi>",
                "commands.tpdeny.usage": "/tpdeny <người_chơi>",
            }
            for key, value in expected.items():
                self.assertEqual(ftbu.get(key), value, key)
            self.assertEqual(ftblib.get("click_here"), "[Bấm vào đây]")
        finally:
            td.cleanup()

    def test_extracted_mod_overlays_do_not_publish_partial_english_catalogs(self):
        """Books/tooltips extracted from JARs must only add vi_vn overlays."""
        td, path = self.build_zip()
        try:
            with zipfile.ZipFile(path) as zf:
                names = set(zf.namelist())
            self.assertIn("assets/botania/lang/vi_vn.lang", names)
            self.assertNotIn("assets/botania/lang/en_us.lang", names)
            # AstralSorcery's overlay stays vi_vn.lang: it has no
            # runtime_locale_meta record, so no case rename is applied.
            self.assertIn("assets/astralsorcery/lang/vi_vn.lang", names)
            self.assertNotIn("assets/astralsorcery/lang/en_US.lang", names)
        finally:
            td.cleanup()

    def test_archive_contains_all_76_live_enchantment_descriptions(self):
        coverage = json.loads((ROOT / "work" / "audit" / "enchantment_registry_coverage.json").read_text(encoding="utf-8"))
        td, path = self.build_zip()
        try:
            merged = {}
            with zipfile.ZipFile(path) as zf:
                for name in zf.namelist():
                    if name.casefold().endswith("/lang/vi_vn.lang"):
                        merged.update(parse_lang(zf.read(name).decode("utf-8")))
            missing = [row["key"] for row in coverage if row["key"] not in merged]
            self.assertEqual([], missing)
        finally:
            td.cleanup()

    def test_archive_has_no_casefold_collisions(self):
        td, path = self.build_zip()
        try:
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
            folded = [name.casefold() for name in names]
            self.assertEqual(len(folded), len(set(folded)))
        finally:
            td.cleanup()

    def test_every_expanded_lang_family_reaches_full_key_coverage(self):
        """Books and tooltips must ship every translated key under their own namespace.

        `books_bloodmagic` is deliberately absent from the build: the JAR
        registers those 274 guide keys under `bloodmagicguide`, so emitting them
        under `bloodmagic` produced a dead copy. Its live translation is
        asserted by test_every_shipped_namespace_is_one_a_mod_actually_registers.
        """
        families = [
            (ROOT / "source" / "books", lambda stem: stem.replace("books_", ""), ROOT / "work" / "translated"),
            (ROOT / "source" / "tooltips", lambda stem: stem, ROOT / "work" / "translated" / "tooltips"),
        ]
        skip_stems = {"books_bloodmagic"}
        td, path = self.build_zip()
        try:
            shipped = {}
            with zipfile.ZipFile(path) as zf:
                for name in zf.namelist():
                    if name.casefold().endswith("/lang/vi_vn.lang"):
                        namespace = name.split("/")[1]
                        shipped.setdefault(namespace, {}).update(parse_lang(zf.read(name).decode("utf-8")))
            problems = []
            for source_dir, to_namespace, translated_dir in families:
                for source in sorted(source_dir.glob("*.lang")):
                    if source.stem in skip_stems:
                        continue
                    namespace = to_namespace(source.stem)
                    expected = set(build_pack.load_lang(source)[0])
                    actual = set(shipped.get(namespace, {}))
                    if not expected <= actual:
                        problems.append((namespace, len(expected - actual)))
            self.assertEqual([], problems)
            # The skipped family still has to ship in full -- under the namespace
            # the JAR registers, not the one its filename suggests.
            bm_source = set(build_pack.load_lang(ROOT / "source" / "books" / "books_bloodmagic.lang")[0])
            self.assertLessEqual(bm_source, set(shipped.get("bloodmagicguide", {})))
        finally:
            td.cleanup()

    def test_patchouli_and_tconstruct_books_ship_vi_vn_trees(self):
        """Guide books use their own JSON resource trees, not .lang keys."""
        td, path = self.build_zip()
        try:
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
            patchouli = [n for n in names if "/patchouli_books/" in n and "/vi_vn/" in n]
            tconstruct = [n for n in names if n.startswith("assets/tconstruct/book/vi_vn/")]
            source_patchouli = list((ROOT / "source" / "patchouli").rglob("*.json"))
            source_tconstruct = list((ROOT / "source" / "tconstruct").rglob("*.json"))
            self.assertEqual(len(source_patchouli), len(patchouli))
            # Six source JSONs are English-only multiblock/structure definition
            # files with no translatable text; the renderer intentionally ships
            # every prose-bearing JSON plus the shared non-JSON book resources.
            text_json = 0
            for source in source_tconstruct:
                data = json.loads(source.read_text(encoding="utf-8"))
                stack = [data]
                has_text = False
                while stack:
                    value = stack.pop()
                    if isinstance(value, dict):
                        if isinstance(value.get("text"), str) and value["text"].strip():
                            has_text = True
                        stack.extend(value.values())
                    elif isinstance(value, list):
                        stack.extend(value)
                text_json += has_text
            self.assertEqual(text_json, len([n for n in tconstruct if n.endswith(".json")]))
            self.assertFalse([n for n in names if "/patchouli_books/" in n and "/en_us/" in n])
            self.assertFalse([n for n in names if not n.startswith("assets/") and n != "pack.mcmeta"])
        finally:
            td.cleanup()

    def test_patchouli_book_titles_and_landing_pages_are_localized(self):
        td, path = self.build_zip()
        try:
            expected = {
                "assets/alchemistry/lang/vi_vn.lang": {
                    "guide.alchemistry.title": "Alchemistry Guidebook",
                    "guide.alchemistry.landing": "Chào mừng bạn đến với Alchemistry Guidebook. Cuốn sách này sẽ giới thiệu những kiến thức cơ bản về mod.",
                },
                "assets/bewitchment/lang/vi_vn.lang": {
                    "item.bewitchment.book_of_shadows.name": "Book of Shadows",
                    "info.bewitchment.book_of_shadows.landing": "Witchcraft là nghệ thuật cổ xưa về phép thuật và tự nhiên. Cuốn sách này sẽ hướng dẫn bạn tự mình khám phá những bí mật của nó.",
                    "item.bewitchment.codex_infernalis.name": "Codex Infernalis",
                    "info.bewitchment.codex_infernalis.landing": "Chỉ cần cầm cuốn sách này cũng đã thấy có gì đó không ổn… bạn có dám tiếp tục không?",
                },
                "assets/mysticalworld/lang/vi_vn.lang": {
                    "mysticalworld.guidebook.name": "Encyclopædia Mysticum",
                    "mysticalworld.guidebook.landing_text": "Ngoài kia là một thế giới vô cùng bí ẩn! Cuốn sách này sẽ giúp bạn hiểu thêm về nhiều điều kỳ bí và huyền diệu mà bạn có thể bắt gặp.",
                },
                "assets/roots/lang/vi_vn.lang": {
                    "item.roots.roots_guide.name": "The Magic of the Wilds",
                    "info.roots.roots_guide.landing": "Cuốn sách này tập hợp kiến thức về phép thuật tự nhiên, có từ thời các Druid cho đến thời hiện đại.$(br2)Ngày nay, các pháp sư hoang dã tìm cách khám phá những phương thức mới và tái khám phá những phương thức cổ xưa mà thế giới tự nhiên trở thành nguồn phép thuật và biến đổi.",
                },
                "assets/twilightforest/lang/vi_vn.lang": {
                    "item.twilightforest.guide.name": "Traveller's Logbook",
                },
            }
            with zipfile.ZipFile(path) as zf:
                for asset, entries in expected.items():
                    actual = parse_lang(zf.read(asset).decode("utf-8"))
                    for key, value in entries.items():
                        self.assertEqual(actual.get(key), value, f"{asset}: {key}")
        finally:
            td.cleanup()

    def test_literal_patchouli_root_metadata_is_localized(self):
        td, path = self.build_zip()
        try:
            with zipfile.ZipFile(path) as zf:
                extreme = json.loads(zf.read("assets/bigreactors/patchouli_books/erguide/book.json"))
                lightning = json.loads(zf.read("assets/lightningcraft/patchouli_books/guide/book.json"))
                member = locale_member(set(zf.namelist()), "lightningcraft")
                self.assertIsNotNone(member)
                lightning_lang = parse_lang(zf.read(member).decode("utf-8"))
            self.assertEqual(extreme["name"], "The Extreme Book")
            self.assertTrue(extreme["landing_text"].startswith("Chào mừng bạn đến với cẩm nang"))
            self.assertEqual(lightning["name"], "item.lightningcraft:guide_0.name")
            self.assertEqual(lightning_lang[lightning["name"]], "Lightning Guide")
        finally:
            td.cleanup()

    def test_remaining_structured_guides_are_localized(self):
        td, path = self.build_zip()
        try:
            with zipfile.ZipFile(path) as zf:
                chisel = json.loads(zf.read("assets/chisel_guide/guide/index.json"))
                enderio = json.loads(zf.read("assets/enderio/book/vi_vn/modifiers/pickup.json"))
                toolprogression = json.loads(zf.read("assets/toolprogression/book/vi_vn/modifiers/magic_mushroom.json"))
                galacticraft = zf.read("assets/galacticraftcore/manuals/gettingstarted.xml").decode("utf-8")
            self.assertEqual(chisel[0]["text"], "The Chisel!")
            self.assertIn("nhấp chuột phải", chisel[2].lower())
            self.assertIn("dịch chuyển", " ".join(enderio["effects"]).lower())
            self.assertIn("cấp khai thác", " ".join(toolprogression["effects"]).lower())
            self.assertIn("Galacticraft", galacticraft)
            self.assertIn("Mục lục", galacticraft)
            self.assertNotIn("Welcome to the first edition", galacticraft)
        finally:
            td.cleanup()

    def test_non_patchouli_guide_overlays_preserve_source_structure(self):
        import xml.etree.ElementTree as ET

        pairs = [
            (ROOT / "source" / "extra_guides" / "chisel.json", ROOT / "work" / "extra_guides_vi" / "assets" / "chisel_guide" / "guide" / "index.json"),
            (ROOT / "source" / "extra_guides" / "enderio.json", ROOT / "work" / "extra_guides_vi" / "assets" / "enderio" / "book" / "vi_vn" / "modifiers" / "pickup.json"),
            (ROOT / "source" / "extra_guides" / "toolprogression.json", ROOT / "work" / "extra_guides_vi" / "assets" / "toolprogression" / "book" / "vi_vn" / "modifiers" / "magic_mushroom.json"),
        ]

        def json_shape(value):
            if isinstance(value, dict):
                return {key: json_shape(item) for key, item in value.items()}
            if isinstance(value, list):
                return [json_shape(item) for item in value]
            return type(value).__name__

        for source, target in pairs:
            self.assertEqual(json_shape(json.loads(source.read_text(encoding="utf-8"))), json_shape(json.loads(target.read_text(encoding="utf-8"))))

        source_xml = ET.parse(ROOT / "source" / "extra_guides" / "galacticraft.xml").getroot()
        target_xml = ET.parse(ROOT / "work" / "extra_guides_vi" / "assets" / "galacticraftcore" / "manuals" / "gettingstarted.xml").getroot()
        self.assertEqual([(node.tag, node.attrib) for node in source_xml.iter()], [(node.tag, node.attrib) for node in target_xml.iter()])
        for source_node, target_node in zip(source_xml.iter(), target_xml.iter()):
            if source_node.tag not in {"text", "title"}:
                # XML pretty-printing may change indentation-only whitespace; all
                # semantic non-text node content and identifiers must stay exact.
                if (source_node.text or "").strip() or (target_node.text or "").strip():
                    self.assertEqual(source_node.text, target_node.text)

        source_text = [node.text for node in source_xml.iter() if node.tag in {"text", "title"} and node.text and node.text.strip()]
        target_text = [node.text for node in target_xml.iter() if node.tag in {"text", "title"} and node.text and node.text.strip()]
        self.assertEqual(len(source_text), 204)
        self.assertEqual(len(source_text), len(target_text))
        protected_exact = {
            source
            for source, target in zip(source_text, target_text)
            if source == target
        }
        # Exact unchanged nodes are allowed only when they are short official
        # technical/proper names, never prose or a sentence.
        invalid_untouched = [
            text for text in protected_exact
            if len(text.split()) > 4 or any(mark in text for mark in ".:;!?\n")
        ]
        self.assertEqual(invalid_untouched, [], f"Untranslated Galacticraft prose: {invalid_untouched[:5]}")
        self.assertLessEqual(len(protected_exact), 60)
        self.assertFalse(any("NL__" in text or "__NL" in text for text in target_text))

    def test_all_advancement_display_text_is_covered(self):
        inventory = json.loads((ROOT / "work" / "audit" / "advancement_inventory.json").read_text(encoding="utf-8"))
        td, path = self.build_zip()
        try:
            shipped = {}
            with zipfile.ZipFile(path) as zf:
                for name in zf.namelist():
                    # Locale casing follows each JAR (vi_VN.lang for a mod
                    # shipping en_US.lang), so match case-insensitively.
                    if name.casefold().endswith("/lang/vi_vn.lang"):
                        shipped.update(parse_lang(zf.read(name).decode("utf-8")))
                names = set(zf.namelist())
            self.assertEqual(set(inventory["entries"]), set(inventory["entries"]) & set(shipped))
            literal_inventory = json.loads((ROOT / "work" / "audit" / "advancement_literal_inventory.json").read_text(encoding="utf-8"))
            self.assertEqual({item["path"] for item in literal_inventory}, {item["path"] for item in literal_inventory} & names)
        finally:
            td.cleanup()

    def test_advancement_literal_overlays_only_change_display_text(self):
        inventory = json.loads((ROOT / "work" / "audit" / "advancement_literal_inventory.json").read_text(encoding="utf-8"))
        td, path = self.build_zip()
        try:
            with zipfile.ZipFile(path) as zf:
                for item in inventory:
                    source = json.loads((ROOT / "source" / "advancement_literals" / item["source_file"]).read_text(encoding="utf-8"))
                    target = json.loads(zf.read(item["path"]).decode("utf-8"))
                    for data in (source, target):
                        data["display"].pop("title", None)
                        data["display"].pop("description", None)
                    self.assertEqual(source, target)
        finally:
            td.cleanup()

    def test_zip_build_is_byte_for_byte_deterministic(self):
        first_td, first = self.build_zip()
        second_td, second = self.build_zip()
        try:
            self.assertEqual(first.read_bytes(), second.read_bytes())
        finally:
            first_td.cleanup()
            second_td.cleanup()


if __name__ == "__main__":
    unittest.main()
