"""Where the Divine Journey 2 install lives on this machine.

The launcher directory used to be written into a dozen tools as an absolute
path under one Windows account, so a checkout on any other machine -- another
user name, another launcher, another OS -- could not build the pack or read
the mod JARs.

Resolution order:

1. ``DJ2_LAUNCHER`` for an explicit launcher directory, or ``DJ2_INSTANCE``
   and ``DJ2_CLIENT_JAR`` to point at one instance or jar directly.
2. The usual per-platform location of an ElyPrism/Prism/MultiMC install.

Nothing here guesses silently: ask for a path that is not there and you get
the list of directories that were tried.
"""

import os
import platform
from pathlib import Path

MINECRAFT_VERSION = "1.12.2"
INSTANCE_NAME = "Divine Journey 2"

_LAUNCHERS = ("ElyPrismLauncher", "PrismLauncher", "MultiMC")


def _candidate_roots():
    explicit = os.environ.get("DJ2_LAUNCHER")
    if explicit:
        return [Path(explicit)]

    system = platform.system()
    roots = []
    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            roots += [Path(appdata) / name for name in _LAUNCHERS]
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
        roots += [base / name for name in _LAUNCHERS]
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        roots += [base / name for name in _LAUNCHERS]
        roots += [Path.home() / f".{name.lower()}" for name in _LAUNCHERS]
    return roots


def launcher_root(required=True):
    """The launcher directory, or None when it is absent and not required."""
    tried = _candidate_roots()
    for root in tried:
        if root.is_dir():
            return root
    if not required:
        return None
    raise SystemExit(
        "launcher directory not found; set DJ2_LAUNCHER. Tried: "
        + ", ".join(str(p) for p in tried)
    )


def instance_dir(required=True):
    """The .minecraft directory of the Divine Journey 2 instance."""
    explicit = os.environ.get("DJ2_INSTANCE")
    if explicit:
        path = Path(explicit)
        if path.is_dir():
            return path
        if required:
            raise SystemExit(f"DJ2_INSTANCE is not a directory: {path}")
        return None

    root = launcher_root(required=required)
    if root is None:
        return None
    # ElyPrism keeps the game directory as "minecraft", Prism and MultiMC as
    # ".minecraft"; both layouts appear in the wild.
    base = root / "instances" / INSTANCE_NAME
    tried = [base / "minecraft", base / ".minecraft"]
    for path in tried:
        if path.is_dir():
            return path
    if required:
        raise SystemExit(
            "instance not found; set DJ2_INSTANCE. Tried: "
            + ", ".join(str(p) for p in tried)
        )
    return None


def mods_dir(required=True):
    """The instance's mods directory."""
    instance = instance_dir(required=required)
    if instance is None:
        return None
    path = instance / "mods"
    if path.is_dir():
        return path
    if required:
        raise SystemExit(f"mods directory not found: {path}")
    return None


def client_jar(required=True):
    """The vanilla client jar, read for font metrics."""
    explicit = os.environ.get("DJ2_CLIENT_JAR")
    if explicit:
        path = Path(explicit)
        if path.is_file():
            return path
        if required:
            raise SystemExit(f"DJ2_CLIENT_JAR is not a file: {path}")
        return None

    root = launcher_root(required=required)
    if root is None:
        return None
    path = (
        root
        / "libraries"
        / "com"
        / "mojang"
        / "minecraft"
        / MINECRAFT_VERSION
        / f"minecraft-{MINECRAFT_VERSION}-client.jar"
    )
    if path.is_file():
        return path
    if required:
        raise SystemExit(
            f"vanilla client jar required for font metrics: {path}; "
            "set DJ2_CLIENT_JAR"
        )
    return None
