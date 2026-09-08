"""Skip the tests that need a built pack when there is not one.

Most of this suite is integration work bound to a machine with the game
installed: it reads the ZIP under build/, the server pack extracted into
%TEMP%, and the mod JARs in the launcher instance. Rebuilding any of it needs
the vanilla client jar for font metrics, so a clean checkout -- a fresh clone,
or CI -- cannot produce them. Without this, such a checkout reports 40
failures and 14 collection errors that are all missing inputs and no defect,
which buries a real regression among them.

Tests that read only files tracked in git keep running everywhere.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "build" / "DJ2_Viet_Hoa_2.23.4.zip"

# Whole modules whose fixtures open the built artifacts.
NEEDS_ARTIFACTS = {
    "test_build_pack",
    "test_font_and_display_fixes",
    "test_guide_book_prose",
    "test_pending_instance_localization",
    "test_resourcepack_host",
    "test_server_script_localization",
    "test_tone_mark_direction",
}

# In this module the split is per class: the pipeline invariants that read
# source files must keep running, the ones that open artifacts must not.
NEEDS_ARTIFACTS_CLASSES = {
    "FinalAcceptanceTests",
    "ReleasePipelineHardeningTests",
    "ServerOverlayInstallTests",
}

# ReadmeFigureTests straddles the line: four of its checks read work/ reports
# and README itself, the rest open the shipped ZIPs.
NEEDS_ARTIFACTS_TESTS = {
    "test_a_stale_figure_fails_the_check",
    "test_every_documented_figure_is_derived_from_real_data",
    "test_shipped_scripts_are_the_translated_copies",
    "test_shipped_trophy_names_are_vietnamese",
    "test_the_shipped_document_matches_the_current_data",
    "test_trophy_overlay_only_rewrites_the_display_name",
}


def pytest_collection_modifyitems(config, items):
    if PACK.is_file():
        return
    skip = pytest.mark.skip(reason=f"pack not built: {PACK}")
    for item in items:
        module = item.module.__name__.rsplit(".", 1)[-1]
        cls = item.cls.__name__ if item.cls else ""
        if (
            module in NEEDS_ARTIFACTS
            or cls in NEEDS_ARTIFACTS_CLASSES
            or item.name in NEEDS_ARTIFACTS_TESTS
        ):
            item.add_marker(skip)
