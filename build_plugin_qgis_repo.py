#!/usr/bin/env python3
"""
Build a distribution zip for the OFFICIAL QGIS plugin repository
(plugins.qgis.org) that *replaces* the existing EasyDEM listing with this
plugin — without changing any plugin source file.

Why this differs from ``build_plugin.py``
------------------------------------------
plugins.qgis.org identifies a plugin by its **package name**: the single
top-level folder inside the uploaded zip. That id is immutable across uploads.
EasyDEM is published under the id ``qgis-EasyDEM-plugin`` (see
https://plugins.qgis.org/plugins/qgis-EasyDEM-plugin/, latest version 4.1). To
push *this* plugin as the next EasyDEM release we must therefore:

  1. Pack everything under a top folder named exactly ``qgis-EasyDEM-plugin``
     (so the repo treats it as a new version of that plugin, not a new plugin).
  2. Declare a ``version`` strictly greater than the published 4.1, or the
     upload is rejected. The bump is written into the zip's ``metadata.txt``
     only — the source file is left untouched.
  3. Set the listing ``name`` to ``EasyDEM`` (same: zip-only override).

The plugin runs entirely on relative imports (``from ..services import ...``),
so the top-folder rename is transparent at runtime — no source edit needed. The
only absolute ``farm_tools.*`` imports live in ``tests/``, which never ship.

What is NOT bundled
-------------------
``extlibs/`` (the earthengine/google/native-wheel stack) is excluded, exactly
as in ``build_plugin.py``: the official repo forbids shipping compiled binaries.
The plugin provisions those at runtime via ``extlibs_manager.py`` (unchanged).
NOTE: a manual reviewer may still question the runtime binary download — that is
a plugin-design point this build cannot and does not alter.

Usage (from OSGeo4W Shell):
    python-qgis-ltr build_plugin_qgis_repo.py
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

# --- Repository-replacement identity --------------------------------------
# Top-level folder inside the zip == the plugin id on plugins.qgis.org. MUST be
# EasyDEM's id so this uploads as EasyDEM's next version instead of a new plugin.
PLUGIN_FOLDER = "qgis-EasyDEM-plugin"
ZIP_NAME = "qgis-EasyDEM-plugin"

# Written into the zip's metadata.txt ONLY (source metadata.txt is not touched).
# version MUST be strictly greater than EasyDEM's published 4.1 or the official
# repo rejects the upload. Bump this for each subsequent release.
OVERRIDE_VERSION = "8.0"
OVERRIDE_NAME = "EasyDEM"

PLUGIN_NAME = "FARM tools (EasyDEM replacement build)"
ROOT = Path(__file__).parent.resolve()
DIST_DIR = ROOT / "dist"
ZIP_PATH = DIST_DIR / f"{ZIP_NAME}.zip"

# metadata.txt is handled specially (transformed), so it is NOT in this list.
INCLUDE_FILES = [
    "__init__.py",
    "farm_tools.py",
    "farm_tools_dialog.py",
    "extlibs_manager.py",
    "icon.png",
    "toolbar_icon.png",
    "LICENSE",
]

INCLUDE_DIRS = [
    "view",
    "services",
    "controllers",
    "managers",
    "renderers",
    "tools",
    "workers",
]

# Assets are handpicked, not globbed: only the files loaded at runtime ship.
INCLUDE_ASSETS = [
    "assets/dem_catalog.json",         # services/dem_registry.py
    "assets/farm_analytica_logo.svg",  # dialog footer logo
    "assets/logo_white.svg",           # view/sidebar.py brand button
    "assets/plotly-1.58.5.min.js",     # view/plotly_render.py, view/sar_plot.py
    "assets/ravi.svg",                 # view/welcome.py RAVI card logo
    "assets/climaplots.svg",           # view/welcome.py ClimaPlots card logo
]

SKIP = {"__pycache__", ".git", ".github", "dist", ".mypy_cache", ".pytest_cache"}

# Lowest version the official repo will accept (EasyDEM's current release).
_PUBLISHED_VERSION = (4, 1)


def step(msg: str) -> None:
    print(f"\n[{msg}]")


def run(cmd: list[str]) -> None:
    print(f"  > {' '.join(str(c) for c in cmd)}")
    subprocess.run(cmd, check=True, cwd=ROOT)


def _force_remove(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _version_tuple(text: str) -> tuple:
    parts = []
    for chunk in text.strip().split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def check_version() -> None:
    """Refuse to build a zip the official repo would reject (version <= 4.1)."""
    step("Check version")
    if _version_tuple(OVERRIDE_VERSION) <= _PUBLISHED_VERSION:
        raise SystemExit(
            f"\nERROR: OVERRIDE_VERSION={OVERRIDE_VERSION} is not greater than the "
            f"published EasyDEM {'.'.join(map(str, _PUBLISHED_VERSION))}.\n"
            "plugins.qgis.org rejects uploads that are not strictly newer.\n"
            "Raise OVERRIDE_VERSION (e.g. 4.2) and rebuild."
        )
    print(f"  OK: {OVERRIDE_VERSION} > {'.'.join(map(str, _PUBLISHED_VERSION))}")


def clean_extlibs() -> None:
    step("Clean extlibs")
    target = ROOT / "extlibs"
    if not target.exists():
        print("  extlibs/ already clean")
        return
    try:
        try:
            shutil.rmtree(target, onexc=_force_remove)
        except TypeError:
            shutil.rmtree(target, onerror=_force_remove)
        print("  Removed extlibs/")
        return
    except PermissionError:
        pass
    if sys.platform == "win32":
        result = subprocess.run(
            ["cmd", "/c", "rd", "/s", "/q", str(target)],
            capture_output=True,
        )
        if result.returncode == 0 and not target.exists():
            print("  Removed extlibs/")
            return
    raise SystemExit(
        "\nERROR: Cannot delete extlibs/ — .pyd files are locked by another process.\n"
        "Close QGIS, then retry."
    )


def compile_translations() -> None:
    step("Compile translations")
    run([sys.executable, str(ROOT / "compile_translations.py")])


def _skip(path: Path, relative_to: Path) -> bool:
    rel = path.relative_to(relative_to)
    return any(part in SKIP for part in rel.parts)


def _transformed_metadata() -> bytes:
    """Source metadata.txt with ``name`` and ``version`` overridden for the
    repository-replacement upload. The source file on disk is left unchanged."""
    src = (ROOT / "metadata.txt").read_text(encoding="utf-8")
    out = []
    saw_name = saw_version = False
    for line in src.splitlines(keepends=True):
        if line.startswith("name="):
            out.append(f"name={OVERRIDE_NAME}\n")
            saw_name = True
        elif line.startswith("version="):
            out.append(f"version={OVERRIDE_VERSION}\n")
            saw_version = True
        else:
            out.append(line)
    if not (saw_name and saw_version):
        raise SystemExit(
            "ERROR: metadata.txt missing a 'name=' or 'version=' line to override."
        )
    return "".join(out).encode("utf-8")


def build_zip() -> None:
    step("Build zip")
    DIST_DIR.mkdir(exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:

        # Transformed metadata first (name + version override).
        zf.writestr(f"{PLUGIN_FOLDER}/metadata.txt", _transformed_metadata())
        print(f"  + metadata.txt (name={OVERRIDE_NAME}, version={OVERRIDE_VERSION})")

        for filename in INCLUDE_FILES:
            src = ROOT / filename
            if src.exists():
                zf.write(src, f"{PLUGIN_FOLDER}/{filename}")
                print(f"  + {filename}")
            else:
                print(f"  ! MISSING: {filename}")

        for asset in INCLUDE_ASSETS:
            src = ROOT / asset
            if src.exists():
                zf.write(src, f"{PLUGIN_FOLDER}/{asset}")
                print(f"  + {asset}")
            else:
                print(f"  ! MISSING: {asset}")

        i18n_dir = ROOT / "i18n"
        if i18n_dir.exists():
            qms = sorted(i18n_dir.glob("*.qm"))
            for qm in qms:
                zf.write(qm, f"{PLUGIN_FOLDER}/i18n/{qm.name}")
            print(f"  + i18n/ ({len(qms)} .qm files)")

        for dirname in INCLUDE_DIRS:
            src = ROOT / dirname
            if not src.exists():
                print(f"  ! MISSING dir: {dirname}/")
                continue
            files = [
                item for item in src.rglob("*")
                if item.is_file() and not _skip(item, src)
            ]
            for item in sorted(files):
                zf.write(item, f"{PLUGIN_FOLDER}/{item.relative_to(ROOT)}")
            print(f"  + {dirname}/ ({len(files)} files)")

    size_mb = ZIP_PATH.stat().st_size / 1_048_576
    print(f"\nDone: dist/{ZIP_NAME}.zip ({size_mb:.1f} MB)")
    print(f"Top-level folder / plugin id: {PLUGIN_FOLDER}")
    print("Upload at https://plugins.qgis.org/plugins/qgis-EasyDEM-plugin/ "
          "(Manage → Add version).")


def main() -> None:
    print(f"Building {PLUGIN_NAME} ...")
    check_version()
    # extlibs are NOT bundled (official repo forbids binaries); they are
    # provisioned at runtime by extlibs_manager.py.
    compile_translations()
    build_zip()


if __name__ == "__main__":
    main()
