import hashlib
import importlib.util
import json
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


if __name__ == "__main__":
    unittest.main()
