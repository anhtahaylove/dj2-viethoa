import hashlib
import importlib.util
import json
import sys
import subprocess
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "source" / "server_shared"
SERVER = ROOT.parent / "Divine_Journey_2.23.4_Server_Pack"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release_chain_test = load_module(
    "release_chain_test", ROOT / "tools" / "build_release_chain.py"
)
readme_numbers_test = load_module(
    "readme_numbers_test", ROOT / "tools" / "check_readme_numbers.py"
)


class FinalAcceptanceTests(unittest.TestCase):
    """README calls FINAL_ACCEPTANCE_CURRENT.json the proof of the shipped build.

    It was hand-written, so it drifted: it described an older ZIP than the one
    on disk and still claimed forceUnicodeFont was disabled after that decision
    was reversed. A stale acceptance file is worse than none — it certifies a
    release nobody is serving. These lock it to the real artifacts.
    """

    ACCEPTANCE = ROOT / "build" / "FINAL_ACCEPTANCE_CURRENT.json"
    ARTIFACTS = {
        "resource_pack": "DJ2_Viet_Hoa_2.23.4.zip",
        "client_bundle": "DJ2_Viet_Hoa_2.23.4_Client_Extract_To_Instance.zip",
        "server_overlay": "DJ2_Viet_Hoa_2.23.4_Server_Localization_Overlay.zip",
    }

    def test_acceptance_hashes_match_the_artifacts_on_disk(self):
        record = json.loads(self.ACCEPTANCE.read_text(encoding="utf-8"))
        drift = {}
        for name, filename in self.ARTIFACTS.items():
            data = (ROOT / "build" / filename).read_bytes()
            claimed = record["artifacts"][name]
            actual = {
                "bytes": len(data),
                "sha1": hashlib.sha1(data).hexdigest(),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
            if {k: claimed[k] for k in actual} != actual:
                drift[name] = {"claimed": claimed, "actual": actual}
        self.assertEqual(
            drift, {},
            "the acceptance record certifies artifacts that are not the ones on "
            f"disk, so it proves nothing about the shipped release: {drift}",
        )

    def test_every_synced_evidence_file_matches_its_generated_copy(self):
        """release/ is the shipped evidence; build/ is untracked scratch.

        Five files are generated into build/ and tracked from release/. Nothing
        owned that copy, so the manifest and the three verification reports each
        went three waves stale, describing the wave-18 pack while the artifacts
        beside them had been rebuilt twice. Nothing caught it: the other tests
        read the build/ copies, and SHA256SUMS.txt lists only the ZIPs.

        Driven off release_chain_test.SYNCED_EVIDENCE so a file added to the
        chain is covered here automatically instead of needing a new test.
        """
        release_dir = ROOT / "release" / "DJ2_Viet_Hoa_2.23.4"
        drift = []
        for name in release_chain_test.SYNCED_EVIDENCE:
            generated = ROOT / "build" / name
            shipped = release_dir / name
            if not generated.is_file():
                # build/ is scratch: empty on a fresh clone, and stripped
                # whenever the chain aborts part way. Skipping here made the
                # comparison vanish rather than fail, so a release/ copy with
                # the wrong bytes passed as long as its build/ twin was gone.
                drift.append(f"{name}: no build/ copy to compare against")
                continue
            if not shipped.is_file():
                drift.append(f"{name}: missing from release/")
                continue
            if (
                hashlib.sha256(shipped.read_bytes()).hexdigest()
                != hashlib.sha256(generated.read_bytes()).hexdigest()
            ):
                drift.append(f"{name}: release/ copy differs from build/")
        self.assertEqual(
            [], drift,
            "tracked release evidence disagrees with what the build produced, "
            f"so it describes a different build than the artifacts beside it: {drift}",
        )

    def test_checksums_cover_the_artifacts_actually_in_release(self):
        """SHA256SUMS.txt must hash the release/ bytes, not build/ bytes.

        It lists only the three ZIPs, which is why the evidence files could
        drift undetected; this asserts the part it does cover is honest.
        """
        release_dir = ROOT / "release" / "DJ2_Viet_Hoa_2.23.4"
        sums = release_dir / "SHA256SUMS.txt"
        self.assertTrue(sums.is_file(), "release/ has no SHA256SUMS.txt")
        listed = {}
        for line in sums.read_text(encoding="utf-8").splitlines():
            if line.strip():
                digest, name = line.split(None, 1)
                listed[name.strip().lstrip("*")] = digest
        self.assertEqual(
            sorted(listed), sorted(release_chain_test.ARTIFACTS),
            "SHA256SUMS.txt does not list exactly the release artifacts",
        )
        for name, digest in listed.items():
            target = release_dir / name
            self.assertTrue(target.is_file(), f"{name} listed but absent")
            self.assertEqual(
                hashlib.sha256(target.read_bytes()).hexdigest(), digest,
                f"{name}: SHA256SUMS.txt certifies bytes that are not on disk",
            )

    def test_acceptance_describes_the_font_mode_actually_shipped(self):
        record = json.loads(self.ACCEPTANCE.read_text(encoding="utf-8"))
        claim = json.dumps(record.get("fixes", {}), ensure_ascii=False)
        options = (
            ROOT / "work" / "client_overlay_vi" / "config" / "defaultoptions" / "options.txt"
        ).read_text(encoding="utf-8")
        shipped_forced = "forceUnicodeFont:true" in options
        self.assertTrue(shipped_forced, "sanity: the shipped client forces the unicode font")
        self.assertNotIn(
            "force_unicode_font\": \"disabled", claim,
            "the acceptance record claims forceUnicodeFont is disabled while the "
            "shipped options.txt enables it",
        )

    def test_publish_evidence_describes_the_artifacts_it_ships_beside(self):
        """publish_verification.json is written by a hand-run, not by the chain.

        publish_release.py copies the pack to the hosted paths and downloads it
        back over HTTP, so it cannot run headless inside the chain. That left it
        as the one synced evidence file nothing regenerates: it kept describing
        an 1,869,550-byte client bundle after the bundle grew to 1,908,826, and
        the sync step happily copied the stale report into release/ because a
        byte-identical copy is all it checks.

        Hash equality against build/ cannot catch this -- both copies are stale
        together. Compare the report against the ZIPs instead.
        """
        release_dir = ROOT / "release" / "DJ2_Viet_Hoa_2.23.4"
        report_path = release_dir / "publish_verification.json"
        if not report_path.is_file():
            self.skipTest("publish_verification.json has not been produced yet")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        drift = []
        for key, name in (
            ("resource_pack", "DJ2_Viet_Hoa_2.23.4.zip"),
            ("client_bundle", "DJ2_Viet_Hoa_2.23.4_Client_Extract_To_Instance.zip"),
        ):
            shipped = release_dir / name
            if not shipped.is_file():
                drift.append(f"{key}: {name} is missing from release/")
                continue
            if key not in report:
                # An absent section is not a clean one: it means publish never
                # recorded this artifact, so nothing here would be compared.
                drift.append(f"{key}: publish record has no entry for {name}")
                continue
            payload = shipped.read_bytes()
            if report[key].get("bytes") != len(payload):
                drift.append(
                    f"{key}: report says {report[key].get('bytes')} bytes, "
                    f"{name} is {len(payload)}"
                )
            digest = hashlib.sha256(payload).hexdigest()
            if report[key].get("sha256") != digest:
                # None was tolerated here, which let a record carrying no digest
                # at all count as agreeing with the artifact.
                drift.append(f"{key}: report sha256 does not match {name}")
        self.assertEqual(
            [], drift,
            "the publish record describes different artifacts than the ones "
            f"shipped beside it, so re-run tools/publish_release.py: {drift}",
        )

    def test_acceptance_keeps_the_measured_suite_result(self):
        """Regenerating without --tests must not erase a measured result.

        The chain rebuilds this record on every run. When a run omitted
        --tests, the placeholder overwrote a real summary like "206 passed",
        destroying the evidence that the suite was ever run -- and the chain
        still exited 0, so nothing flagged the loss.
        """
        with tempfile.TemporaryDirectory() as tmp:
            record = Path(tmp) / "FINAL_ACCEPTANCE_CURRENT.json"
            subprocess.run(
                [sys.executable, str(ROOT / "tools" / "build_final_acceptance.py"),
                 "--output", str(record), "--tests", "206 passed"],
                cwd=ROOT, capture_output=True, text=True, check=True,
            )
            subprocess.run(
                [sys.executable, str(ROOT / "tools" / "build_final_acceptance.py"),
                 "--output", str(record)],
                cwd=ROOT, capture_output=True, text=True, check=True,
            )
            kept = json.loads(record.read_text(encoding="utf-8"))["tests"]
            self.assertEqual(
                "206 passed", kept,
                "a run without --tests must carry the measured result forward",
            )

    def test_publish_refuses_to_record_an_unverified_release(self):
        """No resource-pack URL must abort, not write an empty http block.

        The report's only measured field is the HTTP fetch. Writing it with
        http={} kept server_properties_sha1_matches=True and exited 0, so the
        record still read as a successful publish while the proof that the
        pack is reachable had been silently replaced by nothing.
        """
        source = (ROOT / "tools" / "publish_release.py").read_text(encoding="utf-8")
        self.assertIn(
            "raise SystemExit('server.properties has no resource-pack URL",
            source,
            "publish must abort when it cannot verify the served pack",
        )
        guard = source.index("if not url:")
        write = source.index("publish_verification.json")
        self.assertLess(
            guard, write,
            "the guard must run before the record is written, not after",
        )

    def test_lang_gates_refuse_to_skip_an_unreadable_jar(self):
        """A jar a gate cannot open must abort it, not shrink its evidence.

        Both width gates compare against the official translations shipped
        inside the mod jars. Swallowing the read error and continuing left
        them green while quietly measuring against fewer jars than they
        believed, which is the failure mode the whole audit kept finding.
        """
        for name in ("check_button_widths.py", "check_multiline_tooltips.py"):
            source = (ROOT / "tools" / name).read_text(encoding="utf-8")
            with self.subTest(gate=name):
                self.assertNotIn(
                    "except Exception:\n            continue", source,
                    f"{name} must not skip jars it cannot read",
                )
                self.assertIn(
                    "cannot read mod jar", source,
                    f"{name} must name the jar it could not read",
                )

    def test_coverage_refuses_to_measure_past_an_unreadable_jar(self):
        """A jar coverage cannot open must abort it, not shrink in_scope.

        Every English line inside a skipped jar leaves the denominator, so a
        corrupt download makes coverage climb. That is the one failure that
        reads as progress, and it feeds every figure in DOC_DAU_TIEN.md.
        """
        source = (ROOT / "tools" / "measure_coverage.py").read_text(encoding="utf-8")
        self.assertNotIn(
            "except zipfile.BadZipFile:\n            continue", source,
            "measure_coverage must not skip jars it cannot read",
        )
        self.assertIn(
            "cannot read mod jar", source,
            "measure_coverage must name the jar it could not read",
        )
        for fragment in ("cannot read {member}", "cannot parse {member}"):
            self.assertIn(
                fragment, source,
                "measure_coverage must abort on unreadable lang members too",
            )


class ReleasePipelineHardeningTests(unittest.TestCase):
    def test_client_bundle_uses_only_canonical_shared_inputs(self):
        module = load_module("build_client_hardened", ROOT / "tools" / "build_client_bundle.py")
        self.assertEqual(module.SHARED_ROOT.resolve(), SHARED.resolve())
        self.assertNotIn("Divine_Journey_2.23.4_Server_Pack", (ROOT / "tools" / "build_client_bundle.py").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "client.zip"
            entries = module.build(output)
        for rel in (
            "config/tips.cfg",
            "config/ftbutilities.cfg",
            "scripts/JEI/Excavator.zs",
            "scripts/ContentTweaker/ContentTweakerItems.zs",
        ):
            self.assertEqual(entries[rel], (SHARED / rel).read_bytes())

    def test_biome_counter_messages_are_vietnamese_and_logic_is_unchanged(self):
        expected = (
            "Số biome Mortum khớp:",
            "Số biome Hell khớp:",
            "Số biome Magical Forest khớp:",
            "Số biome Ocean khớp:",
        )
        for rel in (
            "scripts/ContentTweaker/ContentTweakerItems.zs",
            "scripts/ModSpecific/ContentTweakerRecipes.zs",
        ):
            text = (SHARED / rel).read_text(encoding="utf-8")
            for message in expected:
                self.assertIn(message, text)
            self.assertNotIn("biome matches:", text)
            self.assertEqual(text.count('checkBiomesAtPositions("Mortum"'), 1)
            self.assertEqual(text.count('checkBiomesAtPositions("Hell"'), 1)
            self.assertEqual(text.count('checkBiomesAtPositions("Magical Forest"'), 1)
            self.assertEqual(text.count('checkBiomesAtPositions("Ocean"'), 1)
            self.assertEqual(text.count("Số biome"), 4)

    def test_server_overlay_is_deterministic_and_allowlisted(self):
        module = load_module("build_server_overlay_test", ROOT / "tools" / "build_server_overlay.py")
        with tempfile.TemporaryDirectory() as td:
            a = Path(td) / "a.zip"
            b = Path(td) / "b.zip"
            module.build(a)
            module.build(b)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            with zipfile.ZipFile(a) as zf:
                self.assertIsNone(zf.testzip())
                names = set(zf.namelist())
                self.assertEqual(names, set(module.ALLOWED_ENTRIES))
                self.assertFalse(any(re.search(r"(^|/)(?:server\.properties|ops\.json|whitelist\.json|world|logs|backups)(/|$)", n, re.I) for n in names))
                self.assertEqual(zf.read("resourcepack/DJ2_Viet_Hoa_2.23.4.zip"), (ROOT / "build" / "DJ2_Viet_Hoa_2.23.4.zip").read_bytes())

    def test_server_delivery_gate_detects_and_accepts_hash_state(self):
        module = load_module("server_delivery_gate_test", ROOT / "tools" / "verify_server_delivery.py")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pack = root / "canonical.zip"
            hosted = root / "resourcepack" / "canonical.zip"
            hosted.parent.mkdir(parents=True)
            pack.write_bytes(b"canonical bytes")
            hosted.write_bytes(pack.read_bytes())
            sha1 = hashlib.sha1(pack.read_bytes()).hexdigest()
            props = root / "server.properties"
            props.write_text(f"resource-pack=http\\://example.invalid/canonical.zip\nresource-pack-sha1={sha1}\n", encoding="iso-8859-1")
            result = module.verify(pack, hosted, props)
            self.assertTrue(result["ok"])
            hosted.write_bytes(b"stale")
            self.assertFalse(module.verify(pack, hosted, props)["ok"])

    def test_every_hosted_pack_copy_matches_canonical(self):
        canonical = (ROOT / "build" / "DJ2_Viet_Hoa_2.23.4.zip").read_bytes()
        server = ROOT.parent / "Divine_Journey_2.23.4_Server_Pack"
        stale = []
        for path in server.rglob("DJ2_Viet_Hoa_2.23.4.zip"):
            rel = path.relative_to(server).as_posix()
            if "backup" in rel.lower():
                continue
            if path.read_bytes() != canonical:
                stale.append(rel)
        self.assertEqual(stale, [])

    def test_server_overlay_installer_is_idempotent_and_preserves_nontext_ftb_config(self):
        module = load_module("install_server_overlay_test", ROOT / "tools" / "install_server_overlay.py")
        merge = load_module("merge_server_overlay_test", ROOT / "tools" / "merge_instance_ftbutilities.py")
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td)
            server = temp / "server"
            (server / "config").mkdir(parents=True)
            live = ROOT / "work" / "testdata" / "ftbutilities_live.cfg"
            (server / "config" / "ftbutilities.cfg").write_bytes(live.read_bytes())
            (server / "server.properties").write_text(
                "resource-pack=http\\://example.invalid/DJ2_Viet_Hoa_2.23.4.zip\n"
                "resource-pack-sha1=0000000000000000000000000000000000000000\n",
                encoding="iso-8859-1",
            )
            original_nontext = merge.without_reviewed_text(server / "config" / "ftbutilities.cfg")
            overlay = ROOT / "build" / "DJ2_Viet_Hoa_2.23.4_Server_Localization_Overlay.zip"
            module.install(server, overlay, temp / "backup-1")
            first = (server / "config" / "ftbutilities.cfg").read_bytes()
            module.install(server, overlay, temp / "backup-2")
            self.assertEqual((server / "config" / "ftbutilities.cfg").read_bytes(), first)
            self.assertEqual(merge.without_reviewed_text(server / "config" / "ftbutilities.cfg"), original_nontext)

    def test_release_manifest_has_only_current_artifacts(self):
        module = load_module("release_manifest_test", ROOT / "tools" / "build_release_manifest.py")
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "manifest.json"
            data = module.build(output)
        self.assertEqual(data["schema"], 1)
        self.assertEqual(set(data["artifacts"]), {
            "DJ2_Viet_Hoa_2.23.4.zip",
            "DJ2_Viet_Hoa_2.23.4_Client_Extract_To_Instance.zip",
            "DJ2_Viet_Hoa_2.23.4_Server_Localization_Overlay.zip",
        })
        for name, item in data["artifacts"].items():
            path = ROOT / "build" / name
            self.assertEqual(item["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_build_refuses_to_overwrite_a_locked_artifact(self):
        """A held-open ZIP must abort the build, not produce a hybrid archive.

        Windows cannot unlink a file another process has open. The builder used
        to let that PermissionError escape from pathlib, but only after the
        rebuild had already begun -- the ZIP on disk ended up neither the old
        release nor the new one, hashing differently from both. Every evidence
        check then disagreed for a reason none of them could name, and the
        obvious reading (a non-deterministic build) was wrong.
        """
        pack = ROOT / "build" / "DJ2_Viet_Hoa_2.23.4.zip"
        if not pack.is_file():
            self.skipTest("no built pack to lock")
        before = pack.read_bytes()
        with zipfile.ZipFile(pack):
            result = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "build_pack.py")],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(
            result.returncode, 0, "the build must fail while the ZIP is locked"
        )
        message = (result.stderr or "") + (result.stdout or "")
        self.assertIn(
            "holding it open",
            message,
            "the failure must name the cause, not surface a bare WinError",
        )
        self.assertEqual(
            before,
            pack.read_bytes(),
            "a refused rebuild must leave the previous artifact byte-identical",
        )
        # The cleanup handler used to call drop_previous_artifact() before
        # _discard_partials(). On this very path that call raises SystemExit a
        # second time, so the scratch removal never ran and every suite run
        # seeded .partial debris beside the shipped ZIP.
        debris = sorted(
            path.name
            for path in (ROOT / "build").glob("*")
            if "partial" in path.name
        )
        self.assertEqual(
            debris, [], "a refused rebuild must not leave scratch copies behind"
        )

    def test_publish_leaves_no_debris_when_the_host_holds_the_pack(self):
        """A refused publish must not drop a stray temp file in the served dir.

        atomic_copy stages the new pack beside the destination so the rename
        stays on one volume -- but that directory is the one the HTTP host
        serves. Windows refuses the replace while the host has the pack open,
        and an uncleaned staging file leaves a second 1.9 MB archive sitting in
        the directory players download from.
        """
        served = SERVER / "resourcepack" / "DJ2_Viet_Hoa_2.23.4.zip"
        if not served.is_file():
            self.skipTest("no published pack to lock")
        before = served.read_bytes()
        with zipfile.ZipFile(served):
            result = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "publish_release.py")],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(
            result.returncode, 0, "publish must fail while the pack is locked"
        )
        self.assertEqual(
            before, served.read_bytes(), "the served pack must be untouched"
        )
        debris = sorted(p.name for p in served.parent.glob("tmp*"))
        self.assertEqual(
            [], debris, f"publish left staging files behind: {debris}"
        )


class ServerOverlayInstallTests(unittest.TestCase):
    def test_the_installer_covers_every_file_the_overlay_ships(self):
        """A hardcoded install list silently strands newly shipped files.

        The installer copied a fixed tuple of five paths while the overlay
        shipped eight. HandFramingUses.zs was added to the overlay and never
        added here, so the server only ever received it because an unrelated
        publish step happened to copy it -- an edit to that script would not
        have reached the server at all.
        """
        overlay = ROOT / "build" / "DJ2_Viet_Hoa_2.23.4_Server_Localization_Overlay.zip"
        if not overlay.is_file():
            self.fail(f"the overlay must be built before this check: {overlay}")
        installer = load_module("install_server_overlay",
                                ROOT / "tools" / "install_server_overlay.py")
        with zipfile.ZipFile(overlay) as archive:
            shipped = {n for n in archive.namelist() if not n.endswith("/")}
        covered = set(installer.DOC_ENTRIES)
        runtime = shipped - covered
        self.assertTrue(runtime, "the overlay must ship runtime content")
        # Nothing may be listed as documentation unless the overlay ships it.
        self.assertTrue(
            covered <= shipped,
            f"installer names files the overlay does not ship: {sorted(covered - shipped)}",
        )
        with tempfile.TemporaryDirectory() as tmp:
            server = Path(tmp) / "server"
            for rel in sorted(shipped):
                target = server / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"stale")
            # The installer also rewrites server.properties and merges
            # ftbutilities.cfg; give it the real files to work against.
            for rel in ("server.properties", "config/ftbutilities.cfg"):
                real = SERVER / rel
                if real.is_file():
                    target = server / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(real.read_bytes())
            installer.install(server=server, overlay=overlay,
                              backup_root=Path(tmp) / "backup")
            with zipfile.ZipFile(overlay) as archive:
                stranded = [rel for rel in sorted(shipped)
                            if (server / rel).read_bytes() != archive.read(rel)]
        self.assertEqual(
            [], stranded,
            "every file the overlay ships must be installed, not just a fixed list",
        )


class SharedSourceCoverageTests(unittest.TestCase):
    # ftbutilities.cfg is merged key-by-key into the server's existing config
    # rather than shipped whole, and the manifest describes the source tree.
    NOT_SHIPPED_WHOLE = {"SOURCE_MANIFEST.json", "config/ftbutilities.cfg"}

    def test_every_shared_source_file_is_shipped_or_declared_exempt(self):
        """A translated file added to source/ must not silently go unshipped.

        SHARED_ENTRIES is a hand-maintained list. Adding a file to
        source/server_shared/ without adding it there produced a green suite
        while the file reached neither the overlay nor the client -- the exact
        gap that kept HandFramingUses.zs out of the installer.
        """
        overlay = load_module("build_server_overlay",
                               ROOT / "tools" / "build_server_overlay.py")
        on_disk = {
            path.relative_to(SHARED).as_posix()
            for path in SHARED.rglob("*") if path.is_file()
        }
        self.assertTrue(on_disk, f"no shared source files found under {SHARED}")
        unshipped = on_disk - set(overlay.SHARED_ENTRIES) - self.NOT_SHIPPED_WHOLE
        self.assertEqual(
            set(), unshipped,
            "shared source files reach no artifact; add them to SHARED_ENTRIES "
            f"or to NOT_SHIPPED_WHOLE with a reason: {sorted(unshipped)}",
        )
        # An exemption must name a file that exists, or it is hiding a typo.
        stale = self.NOT_SHIPPED_WHOLE - on_disk
        self.assertEqual(set(), stale, f"exemption names missing files: {sorted(stale)}")
        # Every declared entry must exist on disk.
        missing = set(overlay.SHARED_ENTRIES) - on_disk
        self.assertEqual(set(), missing, f"SHARED_ENTRIES names missing files: {sorted(missing)}")


class ReadmeFigureTests(unittest.TestCase):
    """DOC_DAU_TIEN.md is prose no builder rewrites, so it drifts silently.

    It shipped for three waves quoting 20,119 translated lines and 74.3%
    coverage while the stores held 22,618 and 83.5%, and every gate stayed
    green because no gate read it. These tests pin the checker itself: that it
    reads live data rather than constants, and that the chain still runs it.
    """

    def test_every_documented_figure_is_derived_from_real_data(self):
        # Not a golden list: each expectation must come back from the coverage
        # report, the tier file, the quest store or the built pack. A checker
        # that hard-coded today's numbers would pass while the document rots.
        coverage = json.loads((ROOT / "work" / "coverage_report.json").read_text(encoding="utf-8"))
        figures = {label: want for label, _, want in readme_numbers_test.expected()}
        self.assertEqual(figures["coverage percent"],
                         str(coverage["coverage_pct"]).replace(".", ","))
        self.assertEqual(figures["translated lines"],
                         readme_numbers_test.vi(coverage["translated"]))
        self.assertEqual(figures["identical to English"],
                         readme_numbers_test.vi(coverage["identical_to_english"]))
        self.assertGreaterEqual(len(figures), 17)

    def test_the_shipped_document_matches_the_current_data(self):
        self.assertEqual(readme_numbers_test.main(), 0)

    def test_a_stale_figure_fails_the_check(self):
        document = readme_numbers_test.DOC
        original = document.read_bytes()
        # Drift the coverage percentage the document currently states. Pinning
        # a literal here meant the test broke whenever coverage legitimately
        # moved, so read the live figure instead of hardcoding one.
        report = json.loads(
            (ROOT / "work" / "coverage_report.json").read_text(encoding="utf-8"))
        current = f"**{report['coverage_pct']:.1f}%**".replace(".", ",")
        self.assertIn(current.encode("utf-8"), original,
                      f"the document should state the measured coverage {current}")
        mutated = original.replace(current.encode("utf-8"),
                                   "**74,3%**".encode("utf-8"), 1)
        self.assertNotEqual(mutated, original, "mutation did not change the file")
        try:
            document.write_bytes(mutated)
            self.assertEqual(readme_numbers_test.main(), 1)
        finally:
            document.write_bytes(original)
        self.assertEqual(document.read_bytes(), original)

    def test_the_chain_runs_the_readme_check_after_coverage(self):
        scripts = [script for script, _ in release_chain_test.STEPS]
        self.assertIn("check_readme_numbers.py", scripts)
        # The figures come from the stores, so coverage and the tier file must
        # be regenerated before the document is judged against them.
        self.assertLess(scripts.index("measure_coverage.py"),
                        scripts.index("check_readme_numbers.py"))
        self.assertLess(scripts.index("tier_missing.py"),
                        scripts.index("check_readme_numbers.py"))

    def test_coverage_is_measured_after_the_pack_it_reads_is_built(self):
        # measure_coverage.py opens the built ZIP. Running it before
        # build_pack.py measured the previous run's pack, so a stale or
        # half-written archive wrote wrong totals into coverage_report.json
        # and the README gates failed against figures no source change
        # explained (namespaces 169 -> 153, coverage 84,1% -> 71,8%).
        scripts = [script for script, _ in release_chain_test.STEPS]
        self.assertLess(scripts.index("build_pack.py"),
                        scripts.index("measure_coverage.py"))

    def test_the_artifact_skip_list_names_tests_that_exist(self):
        """conftest.py skips by literal name; a rename must not silently stop it.

        The names there decide what runs on a checkout with no built pack. A
        stale entry skips nothing and the test fails in CI for a missing ZIP;
        this catches the rename instead.
        """
        import conftest

        source = (ROOT / "tools" / "test_release_pipeline_hardening.py").read_text(
            encoding="utf-8"
        )
        defined = set(re.findall(r"def (test_\w+)\(", source))
        listed = conftest.NEEDS_ARTIFACTS_TESTS
        self.assertEqual(
            listed - defined,
            set(),
            "conftest.NEEDS_ARTIFACTS_TESTS names tests that no longer exist",
        )

        modules = {p.stem for p in (ROOT / "tools").glob("test_*.py")}
        self.assertEqual(
            conftest.NEEDS_ARTIFACTS - modules,
            set(),
            "conftest.NEEDS_ARTIFACTS names modules that no longer exist",
        )

        classes = set(re.findall(r"^class (\w+)\(", source, re.MULTILINE))
        self.assertEqual(
            conftest.NEEDS_ARTIFACTS_CLASSES - classes,
            set(),
            "conftest.NEEDS_ARTIFACTS_CLASSES names classes that no longer exist",
        )

    def test_the_tier_file_the_readme_quotes_is_built_by_the_chain(self):
        # missing_by_tier.json fed the README's per-tier table while only ever
        # being written by hand, so the tiers could describe a different wave
        # than the totals beside them.
        self.assertIn("tier_missing.py", [script for script, _ in release_chain_test.STEPS])

    def test_shipped_trophy_names_are_vietnamese(self):
        """Trophy names are NBT literals inside give commands, not lang keys.

        config/triumph/script/ (the advancement titles) was translated while
        config/triumph/functions/ (the trophy handed out as the reward) was
        missed: half of one feature shipped in Vietnamese. Coverage cannot see
        these strings at all, so nothing failed. Gate the shipped bytes.
        """
        bundle = ROOT / "build" / "DJ2_Viet_Hoa_2.23.4_Client_Extract_To_Instance.zip"
        vietnamese = re.compile("[\u00c0-\u1ef9]")
        found = []
        with zipfile.ZipFile(bundle) as archive:
            for name in archive.namelist():
                if not name.startswith("config/triumph/functions/triumph/"):
                    continue
                text = archive.read(name).decode("utf-8")
                found.extend(re.findall(r'TrophyName:"([^"]*)"', text))
        self.assertEqual(len(found), 26)
        self.assertEqual([n for n in found if not vietnamese.search(n)], [])

    def test_trophy_overlay_only_rewrites_the_display_name(self):
        """The give command carries item ids, counts and colours beside the name.

        A careless rewrite would corrupt the NBT and silently break the reward,
        so everything except TrophyName must stay byte-identical to upstream.
        """
        upstream = SERVER / "config" / "triumph" / "functions" / "triumph"
        overlay = ROOT / "work" / "client_overlay_vi" / "config" / "triumph" / "functions" / "triumph"

        def placeholder(text):
            return re.sub(r'TrophyName:"[^"]*"', 'TrophyName:"X"', text)

        checked = 0
        for source in sorted(upstream.glob("*.txt")):
            translated = overlay / source.name
            self.assertTrue(translated.is_file(), source.name)
            self.assertEqual(placeholder(source.read_text(encoding="utf-8")),
                             placeholder(translated.read_text(encoding="utf-8")),
                             source.name)
            checked += 1
        self.assertEqual(checked, 27)

    def test_client_ships_every_shared_script_the_server_ships(self):
        """The server overlay and the client bundle must agree on shared scripts.

        ContentTweakerRecipes.zs was translated and shipped to the server while
        the client bundle kept the English copy, so the same biome counter read
        Vietnamese in multiplayer and English in singleplayer. Neither builder
        could see the other, so nothing caught the split.
        """
        server = load_module("build_server_overlay_scripts", ROOT / "tools" / "build_server_overlay.py")
        client = load_module("build_client_bundle_scripts", ROOT / "tools" / "build_client_bundle.py")
        shared_on_server = {e for e in server.SHARED_ENTRIES if e.startswith("scripts/")}
        self.assertTrue(shared_on_server)
        self.assertEqual(shared_on_server - set(client.SERVER_SCRIPT_OVERLAYS), set())

    def test_shipped_scripts_are_the_translated_copies(self):
        """Both bundles must carry the reviewed overlay, not the upstream file."""
        bundle = ROOT / "build" / "DJ2_Viet_Hoa_2.23.4_Client_Extract_To_Instance.zip"
        client = load_module("build_client_bundle_bytes", ROOT / "tools" / "build_client_bundle.py")
        with zipfile.ZipFile(bundle) as archive:
            for relative in client.SERVER_SCRIPT_OVERLAYS:
                self.assertEqual(archive.read(relative),
                                 (SHARED / relative).read_bytes(), relative)


if __name__ == "__main__":
    unittest.main()
