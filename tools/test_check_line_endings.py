"""Tests for the line-ending gate.

The interesting cases are the two real bugs this gate exists to catch (an LF
tool file rewritten as CRLF, and a CRLF data file rewritten as LF) plus the
false positives it must NOT raise, since this repo deliberately mixes styles.
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_line_endings

ROOT = Path(__file__).resolve().parents[1]


class ClassifyTests(unittest.TestCase):
    def test_names_each_newline_style(self):
        self.assertEqual(check_line_endings.classify(b"a\nb\n"), "lf")
        self.assertEqual(check_line_endings.classify(b"a\r\nb\r\n"), "crlf")
        self.assertEqual(check_line_endings.classify(b"a\r\nb\n"), "mixed")
        self.assertEqual(check_line_endings.classify(b"no newline"), "none")

    def test_a_stray_carriage_return_is_not_folded_into_lf(self):
        # Classic-Mac endings would corrupt a .lang value just as badly, so they
        # must not be reported as a clean single style.
        self.assertEqual(check_line_endings.classify(b"a\rb\r\nc\r\n"), "mixed")

    def test_crlf_is_not_miscounted_as_containing_bare_lf(self):
        # The naive `data.count(b"\n")` reading would call this "mixed".
        self.assertEqual(check_line_endings.classify(b"x\r\n" * 50), "crlf")


class ScopeTests(unittest.TestCase):
    def test_checks_the_deliverable_and_the_tools_that_write_it(self):
        self.assertTrue(check_line_endings.is_checked("work/translated/x.json"))
        self.assertTrue(check_line_endings.is_checked("source/foo/bar.lang"))
        self.assertTrue(check_line_endings.is_checked("tools/build_pack.py"))

    def test_skips_generated_trees_and_binaries(self):
        self.assertFalse(check_line_endings.is_checked("build/pack.zip"))
        self.assertFalse(
            check_line_endings.is_checked("release/DJ2/DJ2.zip")
        )
        self.assertFalse(check_line_endings.is_checked("work/backups/w19/a.json"))
        self.assertFalse(check_line_endings.is_checked("instance/mods/a.jar"))


class RepositoryStateTests(unittest.TestCase):
    """The gate itself, run against the real working tree."""

    def test_the_working_tree_has_no_line_ending_drift(self):
        problems = check_line_endings.findings()
        self.assertEqual(problems, [], f"line-ending drift: {problems}")

    def test_committed_styles_reads_blobs_in_one_batch(self):
        # Both styles must survive the batch parser; getting the blob-size
        # arithmetic wrong would desynchronise every subsequent file.
        paths = [
            "tools/build_pack.py",
            "work/translated/runtime_locales/journeymap.json",
        ]
        styles = check_line_endings.committed_styles(paths)
        self.assertEqual(styles.get("tools/build_pack.py"), "lf")
        self.assertEqual(
            styles.get("work/translated/runtime_locales/journeymap.json"), "crlf"
        )

    def test_uncommitted_paths_are_reported_as_absent(self):
        styles = check_line_endings.committed_styles(["tools/not_a_real_file.py"])
        self.assertNotIn("tools/not_a_real_file.py", styles)

    def test_batch_stays_aligned_when_a_missing_path_is_interleaved(self):
        # A `missing` header carries no blob, so the reader must not skip a
        # payload for it; if it does, the following file's style comes back wrong.
        styles = check_line_endings.committed_styles(
            [
                "tools/build_pack.py",
                "tools/not_a_real_file.py",
                "work/translated/runtime_locales/journeymap.json",
            ]
        )
        self.assertEqual(styles.get("tools/build_pack.py"), "lf")
        self.assertEqual(
            styles.get("work/translated/runtime_locales/journeymap.json"), "crlf"
        )


class MutationTests(unittest.TestCase):
    """Flip a real file's newline style and require the gate to notice."""

    def _rewrite(self, rel_path, transform):
        path = ROOT / rel_path
        original = path.read_bytes()
        self.addCleanup(path.write_bytes, original)
        path.write_bytes(transform(original))
        return original

    def _drift_for(self, rel_path):
        return [p for p in check_line_endings.findings() if p["path"] == rel_path]

    def test_detects_an_lf_tool_file_rewritten_as_crlf(self):
        # The build_pack.py refactor bug: Path.write_text() on Windows.
        rel = "tools/build_pack.py"
        self._rewrite(rel, lambda data: data.replace(b"\n", b"\r\n"))
        drift = self._drift_for(rel)
        self.assertEqual(len(drift), 1)
        self.assertEqual(drift[0]["expected"], "lf")
        self.assertEqual(drift[0]["actual"], "crlf")

    def test_detects_a_crlf_data_file_rewritten_as_lf(self):
        # The mirror image, as hit when normalising a store that was CRLF.
        rel = "work/translated/runtime_locales/journeymap.json"
        self._rewrite(rel, lambda data: data.replace(b"\r\n", b"\n"))
        drift = self._drift_for(rel)
        self.assertEqual(len(drift), 1)
        self.assertEqual(drift[0]["expected"], "crlf")
        self.assertEqual(drift[0]["actual"], "lf")

    def test_a_content_edit_in_the_right_style_is_not_flagged(self):
        # The gate must stay quiet for ordinary translation work, otherwise it
        # would fire on every wave and get switched off. Add a real line in the
        # file's own style: content changed, newline style did not.
        rel = "work/translated/runtime_locales/journeymap.json"
        self._rewrite(
            rel,
            lambda data: data.replace(
                b"{\r\n", b'{\r\n  "zz.gate.probe": "probe",\r\n', 1
            ),
        )
        self.assertEqual(check_line_endings.classify((ROOT / rel).read_bytes()), "crlf")
        self.assertEqual(self._drift_for(rel), [])

    def test_restores_cleanly_so_the_gate_goes_quiet_again(self):
        rel = "tools/build_pack.py"
        original = self._rewrite(rel, lambda data: data.replace(b"\n", b"\r\n"))
        self.assertTrue(self._drift_for(rel))
        (ROOT / rel).write_bytes(original)
        self.assertEqual(self._drift_for(rel), [])


class CommandLineTests(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "tools" / "check_line_endings.py"), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def test_exits_zero_on_a_clean_tree(self):
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_exits_one_and_names_the_file_when_a_style_flips(self):
        path = ROOT / "tools" / "build_pack.py"
        original = path.read_bytes()
        self.addCleanup(path.write_bytes, original)
        path.write_bytes(original.replace(b"\n", b"\r\n"))

        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("tools/build_pack.py", result.stdout)
        self.assertIn("HEAD=lf", result.stdout)

    def test_json_mode_is_machine_readable(self):
        result = self._run("--json")
        self.assertEqual(result.returncode, 0)
        self.assertIn('"errors"', result.stdout)


if __name__ == "__main__":
    unittest.main()
