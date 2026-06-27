#!/usr/bin/env python3
"""
Build script: clean extlibs, reinstall deps, compile translations, zip for distribution.

Usage (from OSGeo4W Shell):
    python-qgis-ltr build_plugin.py
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

PLUGIN_NAME = "FARM tools"
ZIP_NAME = "farm_tools"  # output filename; matches repository update pipeline
PLUGIN_FOLDER = "farm_tools"  # zip subfolder; must match install dir name
ROOT = Path(__file__).parent.resolve()
DIST_DIR = ROOT / "dist"
ZIP_PATH = DIST_DIR / f"{ZIP_NAME}.zip"
PACKAGING_DIR = ROOT / "packaging"

# Single-module spin-offs. Each builds the FULL codebase but ships a generated
# _build_flavor.py so module_prefs defaults to showing only that module; the
# rest stay discoverable via the welcome hub's "More tools" strip.
#
# ``folder`` is the zip's top directory == the plugin's package id on
# plugins.qgis.org. For already-published plugins it MUST match exactly so the
# upload registers as a new version (verified against the live repo). Per-module
# metadata.txt and icon.png live under packaging/<key>/.
#
#   key          published package id        status
#   optical      ravi                        published (was v7.0)
#   radar        AGLgis                       published (was v2.0)
#   download     qgis-EasyDEM-plugin          published (was v4.1)
#   climaplots   climaplots                   published (was v2.0)
#   fieldguide   fieldguide                   published (was v2.0)
#   landsat      farm_multi_satellite         new
#   sysi         farm_sysi                    new
#   mapbiomas    farm_mapbiomas               new
FLAVORS = {
    "optical": "ravi",
    "radar": "AGLgis",
    "download": "qgis-EasyDEM-plugin",
    "climaplots": "climaplots",
    "fieldguide": "fieldguide",
    "landsat": "farm_multi_satellite",
    "sysi": "farm_sysi",
    "mapbiomas": "farm_mapbiomas",
}

INCLUDE_FILES = [
    "metadata.txt",
    "__init__.py",
    "farm_tools.py",
    "farm_tools_dialog.py",
    "extlibs_manager.py",
    "requirements.txt",  # needed at runtime: extlibs_manager pip fallback reads it
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
# Source artwork (logo.svg, farm.svg, farm_icon.png), website-only images
# (whatsapp.svg) and orphaned pages (intro_sar.html) stay out of the zip.
INCLUDE_ASSETS = [
    "assets/dem_catalog.json",       # services/dem_registry.py
    "assets/farm_analytica_logo.svg",  # dialog footer logo
    "assets/logo_white.svg",           # view/sidebar.py brand button
    "assets/plotly-1.58.5.min.js",   # view/plotly_render.py, view/sar_plot.py
    "assets/ravi.svg",                 # view/welcome.py RAVI card logo
    "assets/climaplots.svg",           # view/welcome.py ClimaPlots card logo
    "assets/sentinel1.svg",            # view/welcome.py radar card logo
    "assets/fieldguide.svg",           # view/welcome.py Field Guide card logo
    "assets/easydem.svg",              # view/welcome.py EasyDEM card logo
]

SKIP = {"__pycache__", ".git", ".github", "dist", ".mypy_cache", ".pytest_cache"}


def step(msg: str) -> None:
    print(f"\n[{msg}]")


def run(cmd: list[str]) -> None:
    print(f"  > {' '.join(str(c) for c in cmd)}")
    subprocess.run(cmd, check=True, cwd=ROOT)


def _force_remove(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)


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


def build_extlibs() -> None:
    step("Install extlibs")
    target = ROOT / "extlibs"
    target.mkdir()
    run([
        sys.executable, "-m", "pip", "install",
        "-r", str(ROOT / "requirements.txt"),
        "--target", str(target),
        "--upgrade", "--no-compile",
    ])


def compile_translations() -> None:
    step("Compile translations")
    run([sys.executable, str(ROOT / "compile_translations.py")])


def _skip(path: Path, relative_to: Path) -> bool:
    rel = path.relative_to(relative_to)
    return any(part in SKIP for part in rel.parts)


def _build_zip(folder: str, zip_path: Path, *,
               metadata_src: Path, icon_src: Path,
               flavor_key: str | None = None) -> None:
    """Zip the codebase under top dir ``folder`` into ``zip_path``.

    ``metadata_src`` / ``icon_src`` override the root metadata.txt / icon.png so
    a flavor ships its own. When ``flavor_key`` is set, a generated
    _build_flavor.py is injected so module_prefs defaults to that module.
    """
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:

        for filename in INCLUDE_FILES:
            if filename == "metadata.txt":
                src = metadata_src
            elif filename == "icon.png":
                src = icon_src
            else:
                src = ROOT / filename
            if src.exists():
                zf.write(src, f"{folder}/{filename}")
            else:
                print(f"  ! MISSING: {filename} ({src})")

        if flavor_key:
            zf.writestr(
                f"{folder}/_build_flavor.py",
                "# Generated by build_plugin.py — do not edit.\n"
                f'FLAVOR = "{flavor_key}"\n',
            )

        for asset in INCLUDE_ASSETS:
            src = ROOT / asset
            if src.exists():
                zf.write(src, f"{folder}/{asset}")
            else:
                print(f"  ! MISSING: {asset}")

        i18n_dir = ROOT / "i18n"
        if i18n_dir.exists():
            for qm in sorted(i18n_dir.glob("*.qm")):
                zf.write(qm, f"{folder}/i18n/{qm.name}")

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
                zf.write(item, f"{folder}/{item.relative_to(ROOT)}")

    size_mb = zip_path.stat().st_size / 1_048_576
    print(f"  Done: dist/{zip_path.name} (top dir '{folder}', {size_mb:.1f} MB)")


def build_full() -> None:
    step("Build FARM tools (full)")
    DIST_DIR.mkdir(exist_ok=True)
    _build_zip(
        PLUGIN_FOLDER, ZIP_PATH,
        metadata_src=ROOT / "metadata.txt",
        icon_src=ROOT / "icon.png",
        flavor_key=None,
    )


def build_flavors() -> None:
    step("Build single-module plugins")
    DIST_DIR.mkdir(exist_ok=True)
    for key, folder in FLAVORS.items():
        meta = PACKAGING_DIR / key / "metadata.txt"
        icon = PACKAGING_DIR / key / "icon.png"
        if not meta.exists() or not icon.exists():
            print(f"  ! SKIP {key}: missing packaging/{key}/metadata.txt or icon.png")
            continue
        _build_zip(
            folder, DIST_DIR / f"{folder}.zip",
            metadata_src=meta, icon_src=icon, flavor_key=key,
        )


def main() -> None:
    print(f"Building {PLUGIN_NAME} + {len(FLAVORS)} single-module plugins ...")
    #clean_extlibs()
    #build_extlibs()
    compile_translations()
    build_full()
    build_flavors()


if __name__ == "__main__":
    main()
