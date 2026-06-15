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

INCLUDE_FILES = [
    "metadata.txt",
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
# Source artwork (logo.svg, farm.svg, ravi.svg, farm_icon.png), website-only
# images (whatsapp.svg) and orphaned pages (intro_sar.html) stay out of the zip.
INCLUDE_ASSETS = [
    "assets/dem_catalog.json",       # services/dem_registry.py
    "assets/farm_analytica_logo.svg",  # dialog footer logo
    "assets/logo_white.svg",           # view/sidebar.py brand button
    "assets/plotly-1.58.5.min.js",   # view/plotly_render.py, view/sar_plot.py
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


def build_zip() -> None:
    step("Build zip")
    DIST_DIR.mkdir(exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:

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
            for qm in sorted(i18n_dir.glob("*.qm")):
                zf.write(qm, f"{PLUGIN_FOLDER}/i18n/{qm.name}")
            print(f"  + i18n/ ({len(list(i18n_dir.glob('*.qm')))} .qm files)")

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


def main() -> None:
    print(f"Building {PLUGIN_NAME} ...")
    #clean_extlibs()
    #build_extlibs()
    compile_translations()
    build_zip()


if __name__ == "__main__":
    main()
