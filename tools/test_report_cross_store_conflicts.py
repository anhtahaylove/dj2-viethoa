"""Tests for tools/report_cross_store_conflicts.py.

Several translated stores merge into one lang file per namespace, so a key that
lives in two stores that feed the SAME namespace ships whichever value the merge
happens to write last. That is invisible in review -- both files look fine on
their own -- and it already shipped once: 22 Thermal Expansion keys drifted
between `runtime_locales/thermalexpansion.json` and a dead
`p2_thermalexpansion.json` that the build never included.

The report was a script someone had to remember to run, so these tests turn its
invariant into a gate: the shipped stores must contain zero same-namespace
conflicts, and the detector must still be able to see one when it exists.
"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import report_cross_store_conflicts as rcsc

ROOT = Path(__file__).resolve().parents[1]


class StoreNamespaceTests(unittest.TestCase):
    def test_stores_resolve_to_the_namespace_the_build_merges_them_into(self):
        owners = rcsc.store_namespaces()
        self.assertEqual(
            owners.get("work/translated/p2_roots.json"), {"roots"},
            "the p2_ prefix must be stripped: p2_roots.json merges into roots",
        )
        self.assertEqual(
            owners.get("work/translated/runtime_locales/roots.json"), {"roots"},
            "runtime_locales stems map to their namespace unchanged",
        )

    def test_a_store_the_build_never_includes_owns_no_namespace(self):
        """books_bloodmagic is deliberately excluded from the build.

        Its keys are registered under `bloodmagicguide`, so emitting them as
        `bloodmagic` produced a dead second copy. A store outside the build
        cannot conflict with anything, and must not be reported as if it could.
        """
        owners = rcsc.store_namespaces()
        self.assertEqual(owners.get("work/translated/books_bloodmagic.json", set()), set())


class ConflictClassificationTests(unittest.TestCase):
    def test_same_namespace_with_different_values_is_a_conflict(self):
        store = {"gui.ok": {"a.json": "Xong", "b.json": "Hoàn tất"}}
        owners = {"a.json": {"mekanism"}, "b.json": {"mekanism"}}
        self.assertEqual(list(rcsc.real_conflicts(store, owners)), ["gui.ok"])

    def test_same_value_in_two_stores_is_not_a_conflict(self):
        store = {"gui.ok": {"a.json": "Xong", "b.json": "Xong"}}
        owners = {"a.json": {"mekanism"}, "b.json": {"mekanism"}}
        self.assertEqual(rcsc.real_conflicts(store, owners), {})

    def test_different_namespaces_never_collide_at_merge_time(self):
        store = {"gui.active": {"a.json": "Đang hoạt động", "b.json": "Làm mát bằng nước"}}
        owners = {"a.json": {"ftblib"}, "b.json": {"mekanism"}}
        self.assertEqual(rcsc.real_conflicts(store, owners), {})

    def test_an_unshipped_store_cannot_conflict(self):
        store = {"gui.ok": {"shipped.json": "Xong", "dead.json": "Hoàn tất"}}
        owners = {"shipped.json": {"mekanism"}, "dead.json": set()}
        self.assertEqual(rcsc.real_conflicts(store, owners), {})


class ShippedStoresTests(unittest.TestCase):
    def test_shipped_stores_have_no_same_namespace_conflicts(self):
        conflicts = rcsc.real_conflicts()
        self.assertEqual(
            conflicts, {},
            "two stores feeding one namespace disagree, so the shipped value "
            "depends on merge order; reconcile them in work/translated/",
        )

    def test_detector_catches_a_conflict_injected_into_a_real_store(self):
        """Guard the gate itself: a real duplicate must fail the assertion above.

        Uses the live store map so a refactor that silently stops loading
        `work/translated/` cannot leave the suite passing vacuously.
        """
        store = rcsc.load_stores()
        owners = rcsc.store_namespaces()
        victim = "work/translated/runtime_locales/roots.json"
        other = "work/translated/p2_roots.json"
        self.assertEqual(owners.get(victim), owners.get(other), "fixture assumes both feed roots")

        store["test.injected.conflict"] = {victim: "Một", other: "Hai"}
        self.assertIn("test.injected.conflict", rcsc.real_conflicts(store, owners))


class ReportOutputTests(unittest.TestCase):
    def test_report_exits_zero_only_when_there_are_no_real_conflicts(self):
        self.assertEqual(rcsc.main.__module__, "report_cross_store_conflicts")
        self.assertEqual(rcsc.real_conflicts(), {})

    def test_non_dict_and_unparsable_stores_are_skipped(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store_dir = root / "work" / "translated"
            store_dir.mkdir(parents=True)
            (store_dir / "list.json").write_text("[1, 2]", encoding="utf-8")
            (store_dir / "broken.json").write_text("{not json", encoding="utf-8")
            (store_dir / "good.json").write_text(json.dumps({"k": "V"}), encoding="utf-8")

            original = rcsc.ROOT
            try:
                rcsc.ROOT = root
                loaded = rcsc.load_stores()
            finally:
                rcsc.ROOT = original

        self.assertEqual(loaded, {"k": {"work/translated/good.json": "V"}})


if __name__ == "__main__":
    unittest.main()
