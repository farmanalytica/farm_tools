# -*- coding: utf-8 -*-
"""Build an extlibs zip tagged for the running Python + platform.

Two modes:

  # Full build (recommended) — run with the TARGET QGIS Python:
  python build_extlibs_zip.py
      pip-installs requirements.txt into a temp dir, strips QGIS-provided
      packages (numpy/pandas/scipy/...), and writes extlibs-<tag>.zip
      (e.g. extlibs-cp312-win_amd64.zip) to the plugin root.

  # Manual mode — zip an existing pip --target dir:
  python build_extlibs_zip.py <build_dir> <out_zip>

Commit + push the resulting extlibs-<tag>.zip so the runtime downloader
(extlibs_manager) can fetch the build matching each QGIS Python. The GitHub
Actions workflow (.github/workflows/build-extlibs.yml) builds the full matrix.

Cross-target builds: set ``_PYTHON_HOST_PLATFORM`` (e.g.
``macosx-10.13-universal2``) to tag the bundle for a platform other than the
host. ``sysconfig.get_platform()`` honours that env var, so the output tag
follows automatically; we additionally pass it to pip as ``--platform`` (with
``--only-binary=:all:``) so wheels for the target platform are downloaded. The
macOS CI job uses this so the bundle matches QGIS's universal2 Python rather
than the arm64 runner.
"""
import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import zipfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REQUIREMENTS = os.path.join(_HERE, "requirements.txt")

# Set by CI to cross-target a platform other than the host (e.g. the macOS job
# sets it to ``macosx-10.13-universal2`` so the bundle matches QGIS, not the
# arm64 runner). sysconfig.get_platform() already returns this verbatim.
#
# On POSIX, sysconfig keys off mere PRESENCE of the var, so an empty value
# (the CI ternary sets "" on non-macOS jobs) would yield a broken "cp312-" tag.
# Scrub an empty value so the host platform is detected normally.
if not os.environ.get("_PYTHON_HOST_PLATFORM"):
    os.environ.pop("_PYTHON_HOST_PLATFORM", None)
_HOST_PLATFORM = os.environ.get("_PYTHON_HOST_PLATFORM")

# Keep in sync with extlibs_manager._QGIS_PROVIDED.
_QGIS_PROVIDED = (
    "numpy", "pandas", "scipy", "matplotlib", "requests", "certifi",
    "urllib3", "idna", "charset_normalizer", "plotly",
)


def current_tag() -> str:
    plat = sysconfig.get_platform().replace("-", "_").replace(".", "_")
    return f"cp{sys.version_info.major}{sys.version_info.minor}-{plat}"


def zip_dir(src, out):
    zf = zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9)
    n = 0
    for root, _, files in os.walk(src):
        for f in files:
            fp = os.path.join(root, f)
            rel = os.path.relpath(fp, src).replace(os.sep, "/")
            zf.write(fp, "extlibs/" + rel)
            n += 1
    zf.close()
    print("files", n, "zip MB", round(os.path.getsize(out) / 1e6, 1))


def _strip(target):
    # remove QGIS-provided packages + junk to shrink the zip
    for entry in list(os.listdir(target)):
        low = entry.lower()
        full = os.path.join(target, entry)
        drop = any(low == p or low.startswith(p + "-") or low.startswith(p + ".")
                   for p in _QGIS_PROVIDED)
        if drop:
            shutil.rmtree(full, ignore_errors=True) if os.path.isdir(full) else os.remove(full)
    for root, dirs, files in os.walk(target):
        for d in list(dirs):
            if d in ("__pycache__", "tests", "test"):
                shutil.rmtree(os.path.join(root, d), ignore_errors=True)
        for f in files:
            if f.endswith((".whl", ".pyc")):
                try:
                    os.remove(os.path.join(root, f))
                except OSError:
                    pass


def patch_climdex(target):
    """climdex uses the deprecated '1M' offset; pandas 3.x rejects it and 9 of
    17 indices fail silently. Replace with 'ME'. Idempotent."""
    base = os.path.join(target, "climdex")
    for name in ("precipitation.py", "temperature.py"):
        f = os.path.join(base, name)
        if not os.path.isfile(f):
            continue
        with open(f, "r", encoding="utf-8") as fh:
            c = fh.read()
        if "'1M'" in c:
            with open(f, "w", encoding="utf-8") as fh:
                fh.write(c.replace("'1M'", "'ME'"))
            print(f"Patched climdex/{name} ('1M' -> 'ME')")


def full_build():
    tag = current_tag()
    # Write to the plugin root (committed + served by the raw GitHub URL that
    # extlibs_manager fetches).
    out = os.path.join(_HERE, f"extlibs-{tag}.zip")
    build = tempfile.mkdtemp(prefix="farm_tools_extlibs_")
    try:
        print(f"pip install -> {build}")
        cmd = [sys.executable, "-m", "pip", "install", "--target", build,
               "-r", _REQUIREMENTS, "--no-warn-script-location"]
        if _HOST_PLATFORM:
            # Cross-target: only-binary so pip downloads target-platform wheels
            # (no sdist builds against the host) for the requested platform.
            pip_plat = _HOST_PLATFORM.replace("-", "_").replace(".", "_")
            plats = [pip_plat]
            # universal2 fallback: several deps (pandas 3.x, pyarrow 19+,
            # bottleneck) publish NO universal2 macOS wheel, only arch-specific
            # ones. pandas is QGIS-provided and stripped, but pip must still
            # RESOLVE it; pyarrow/bottleneck ship in the bundle. Accept both arch
            # sub-platforms so those resolve. pip --platform matches wheels
            # tagged AT OR BELOW the given macOS version, so use a high floor
            # (15_0) -- pyarrow 19+ wheels are tagged macosx_12_0, which the old
            # 11_0/10_13 floors rejected ("No matching distribution for
            # pyarrow"). universal2 stays first => pip prefers it for every
            # package that ships one; arch-only packages fall back to arm64/x86.
            if "universal2" in pip_plat:
                plats += ["macosx_15_0_arm64", "macosx_15_0_x86_64"]
            for p in plats:
                cmd += ["--platform", p]
            cmd += ["--only-binary=:all:"]
            print(f"cross-target platform {pip_plat} (resolve via {plats})")
        subprocess.run(cmd, check=True)
        _strip(build)
        patch_climdex(build)
        zip_dir(build, out)
        print(f"Done: extlibs-{tag}.zip")
    finally:
        shutil.rmtree(build, ignore_errors=True)


def main():
    if len(sys.argv) == 3:
        zip_dir(sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 1:
        full_build()
    else:
        sys.exit("usage: build_extlibs_zip.py [<build_dir> <out_zip>]")


if __name__ == "__main__":
    main()
