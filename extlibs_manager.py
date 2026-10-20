# -*- coding: utf-8 -*-
"""Provision third-party Python deps not bundled with QGIS, matching the
running interpreter.

RAVI needs earthengine-api, agrigee-lite, google-* and their compiled
dependencies (cryptography, cffi, greenlet, ...). Those are NOT shipped with
QGIS and are ABI-locked to the Python version, so a single bundle breaks when
QGIS ships a different Python. numpy/pandas/scipy/requests/etc. DO come with
QGIS and must never be shadowed from extlibs/.

Strategy, in order:
  1. Download a prebuilt zip tagged for this Python+platform
     (``extlibs-<cpXY>-<platform>.zip``).
  2. Fall back to running the QGIS Python's pip to install into ``extlibs/``.
  3. Otherwise report failure (the dialog shows manual instructions).

The active build is recorded in ``extlibs/.ready`` together with its tag, so a
QGIS Python upgrade (different tag) re-provisions automatically.
"""
import hashlib
import importlib
import importlib.metadata
import logging
import os
import shutil
import subprocess
import sys
import sysconfig
import urllib.request
import zipfile

from qgis.PyQt.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

# Prebuilt bundles are published as GitHub Release assets (not committed to the
# repo) so the plugin checkout stays small and the heavy zips never bloat git.
# Bump _EXTLIBS_RELEASE when a new tagged release re-publishes the bundles.
_EXTLIBS_RELEASE = "version15"
BASE_URL = (
    "https://github.com/farmanalytica/farm_tools/releases/download/"
    f"{_EXTLIBS_RELEASE}/"
)
_PLUGIN_DIR = os.path.dirname(__file__)
EXTLIBS_PATH = os.path.join(_PLUGIN_DIR, "extlibs")
_SENTINEL = os.path.join(EXTLIBS_PATH, ".ready")
_REQUIREMENTS = os.path.join(_PLUGIN_DIR, "requirements.txt")

# QGIS user-profile dependencies directory — packages here are on sys.path and
# merge with QGIS's own site-packages via pkgutil.extend_path.  Used for
# PyQt6-WebEngine which must live alongside the existing PyQt6 namespace.
_PROFILE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(_PLUGIN_DIR)))
_DEPS_PATH = os.path.join(
    _PROFILE_DIR, "python", "dependencies",
    f"{sys.version_info.major}.{sys.version_info.minor}",
)
_WEBENGINE_SENTINEL = os.path.join(EXTLIBS_PATH, ".webengine_checked")

# Deps shipped with QGIS itself — never keep them in extlibs/ (ABI shadowing).
_QGIS_PROVIDED = (
    "numpy", "pandas", "scipy", "matplotlib", "requests", "certifi",
    "urllib3", "idna", "charset_normalizer",
)

# Import names that MUST exist in extlibs/ for the plugin to work, mapped to
# the pip requirement that supplies each. A prebuilt zip can be stale (deps
# added to requirements.txt after the bundle was built), so provisioning is
# judged by the presence of these packages, not merely by a successful zip
# extraction. Missing any -> the pip fallback fills the gap.
#
# A ``None`` pip name marks a heavy/transitive core package (agrigee_lite pulls
# the whole earthengine/google stack): if it is missing we reinstall the full
# requirements set rather than name it directly.
_REQUIRED_PACKAGES = {
    "agrigee_lite": None,
    "ee": None,
    "cryptography": None,
    "climdex": "pyclimdex",
    "pymannkendall": "pymannkendall",
    "pyhomogeneity": "pyhomogeneity",
    "xarray": "xarray",
    "bottleneck": "bottleneck",
    "sklearn": "scikit-learn",
}

# Suppress the transient console window the pip subprocess would otherwise pop
# on Windows. 0 on POSIX (subprocess ignores it).
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _pkg_present(pkg: str) -> bool:
    """A package counts as present only when importable: a dir with
    __init__.py or a single-module .py. A bare dir is not enough — an
    interrupted upgrade (locked .pyd while QGIS holds the DLL) can leave a
    gutted package where only the compiled extension survived, which the old
    isdir() check accepted forever."""
    return (
        os.path.isfile(os.path.join(EXTLIBS_PATH, pkg, "__init__.py"))
        or os.path.isfile(os.path.join(EXTLIBS_PATH, pkg + ".py"))
    )


def _missing_pip_specs():
    """pip requirement strings for the required packages absent from extlibs/.

    Returns ``None`` to signal a full requirements.txt reinstall (a core
    package is missing, or one has no direct pip name).
    """
    specs = []
    for pkg, pip_name in _REQUIRED_PACKAGES.items():
        if _pkg_present(pkg):
            continue
        if pip_name is None:
            return None  # core package missing -> full reinstall
        specs.append(pip_name)
    return specs


def _has_web_backend():
    """True if any Qt web view backend is importable."""
    for mod in ("PyQt6.QtWebEngineCore", "PyQt6.QtWebKitWidgets"):
        try:
            importlib.import_module(mod)
            return True
        except ImportError:
            continue
    return False


def _webengine_checked():
    """True if we already attempted WebEngine installation for this tag."""
    try:
        with open(_WEBENGINE_SENTINEL, "r", encoding="utf-8") as f:
            return f.read().strip() == current_tag()
    except Exception:
        return False


def _mark_webengine_checked():
    os.makedirs(EXTLIBS_PATH, exist_ok=True)
    with open(_WEBENGINE_SENTINEL, "w", encoding="utf-8") as f:
        f.write(current_tag())


_downloader = None


def current_tag() -> str:
    """e.g. 'cp312-win_amd64' for the running interpreter."""
    plat = sysconfig.get_platform().replace("-", "_").replace(".", "_")
    return f"cp{sys.version_info.major}{sys.version_info.minor}-{plat}"


def _bundle_tags():
    """Tags to try when fetching a prebuilt zip, most specific first.

    macOS builds report the build host's deployment target and a single arch
    (e.g. 'macosx-15.7-x86_64' on the vcpkg QGIS 3.44 bundle), but releases
    only publish universal2 macOS zips, so fall back to that tag.
    """
    tags = [current_tag()]
    if sys.platform == "darwin":
        universal = (
            f"cp{sys.version_info.major}{sys.version_info.minor}"
            "-macosx_10_13_universal2"
        )
        if universal not in tags:
            tags.append(universal)
    return tags


def _req_fingerprint() -> str:
    """Short hash of requirements.txt so a dependency change re-provisions."""
    try:
        with open(_REQUIREMENTS, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()[:8]  # nosec B324
    except Exception:
        return ""


def _expected_sentinel() -> str:
    return current_tag() + "|" + _req_fingerprint()


def _read_ready_tag():
    try:
        with open(_SENTINEL, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return None


def is_ready() -> bool:
    """Provisioned for THIS interpreter AND this requirements set.

    Legacy sentinels (empty or bare interpreter tag) predate the requirements
    fingerprint and force a one-time re-provision so newly added packages are
    picked up.
    """
    if not os.path.isfile(_SENTINEL):
        return False
    return _read_ready_tag() == _expected_sentinel()


def bundle_complete() -> bool:
    """True when every required package is present in extlibs/.

    Guards against a stale prebuilt zip that extracted cleanly but predates a
    dependency added to requirements.txt (e.g. the ClimaPlots climate stack).
    """
    if not os.path.isdir(EXTLIBS_PATH):
        return False
    return all(_pkg_present(pkg) for pkg in _REQUIRED_PACKAGES)


def needs_provision() -> bool:
    if not os.path.isdir(EXTLIBS_PATH):
        return True
    if not is_ready():
        return True
    # Sentinel can match while the bundle is missing newly-added packages.
    if not bundle_complete():
        return True
    # Some QGIS builds (e.g. macOS 4.2.x) ship without QtWebEngine bindings.
    # Trigger provisioning once to pip-install them into the user deps path.
    if not _has_web_backend() and not _webengine_checked():
        return True
    return False


def ensure_on_path():
    if EXTLIBS_PATH not in sys.path:
        sys.path.insert(0, EXTLIBS_PATH)
    # __init__.py may have inserted EXTLIBS_PATH while the dir was still empty
    # (pre-provision), poisoning Python's path-finder cache for that directory.
    importlib.invalidate_caches()


def get_downloader():
    return _downloader


def start_download(on_done=None):
    """Start (or join) the provisioning thread.

    ``on_done`` is connected BEFORE the thread starts: a fast failure (404 +
    pip unavailable) can emit ``download_done`` within milliseconds, and a
    slot connected after that emission never fires, leaving the loading page
    up forever.
    """
    global _downloader
    if _downloader is not None and _downloader.isRunning():
        if on_done is not None:
            _downloader.download_done.connect(on_done)
        return _downloader
    _downloader = ExtlibsDownloader()
    if on_done is not None:
        _downloader.download_done.connect(on_done)
    _downloader.start()
    return _downloader


def _python_executable():
    """Best-effort path to the QGIS Python interpreter (not the GUI binary)."""
    cands = []
    base_exe = getattr(sys, "_base_executable", None)
    if base_exe:
        cands.append(base_exe)
    if os.name == "nt":
        cands.append(os.path.join(sys.base_exec_prefix, "python.exe"))
        cands.append(os.path.join(sys.exec_prefix, "python.exe"))
    else:
        cands.append(os.path.join(sys.base_exec_prefix, "bin", "python3"))
        cands.append(os.path.join(sys.exec_prefix, "bin", "python3"))
    for name in ("python3", "python"):
        w = shutil.which(name)
        if w:
            cands.append(w)
    for c in cands:
        if c and os.path.basename(c).lower().startswith("python") and os.path.exists(c):
            return c
    return None


def _subprocess_env():
    """Environment for running the QGIS Python as a subprocess.

    macOS QGIS 4.x vcpkg builds embed a Python whose compiled-in prefix
    references the CI build host, so the subprocess crashes with
    ``ModuleNotFoundError: encodings`` unless PYTHONHOME is set to the
    real Frameworks directory.
    """
    env = os.environ.copy()
    if sys.platform == "darwin":
        stdlib_dir = os.path.dirname(os.__file__)
        home = os.path.dirname(os.path.dirname(stdlib_dir))
        pyver = f"python{sys.version_info.major}.{sys.version_info.minor}"
        if os.path.isdir(os.path.join(home, "lib", pyver)):
            env["PYTHONHOME"] = home
    return env


def _strip_qgis_provided(target):
    """Remove QGIS-provided packages from a target dir (avoid ABI shadowing)."""
    try:
        for entry in os.listdir(target):
            low = entry.lower()
            if any(low == p or low.startswith(p + "-") or low.startswith(p + ".")
                   for p in _QGIS_PROVIDED):
                path = os.path.join(target, entry)
                shutil.rmtree(path, ignore_errors=True) if os.path.isdir(path) else os.remove(path)
    except Exception:
        logger.debug("Failed to remove QGIS-provided package from extlibs", exc_info=True)


def _patch_climdex():
    """climdex uses the deprecated '1M' offset; pandas 3.x rejects it and 9 of
    17 indices fail silently. Replace with 'ME'. Idempotent. Applied after a
    pip fallback, which pulls the UNPATCHED climdex (the prebuilt zips are
    already patched by build_extlibs_zip.py)."""
    base = os.path.join(EXTLIBS_PATH, "climdex")
    for name in ("precipitation.py", "temperature.py"):
        f = os.path.join(base, name)
        if not os.path.isfile(f):
            continue
        try:
            with open(f, "r", encoding="utf-8") as fh:
                c = fh.read()
            if "'1M'" in c:
                with open(f, "w", encoding="utf-8") as fh:
                    fh.write(c.replace("'1M'", "'ME'"))
        except Exception:
            logger.debug("Failed to patch climdex '1M' offset in %s", f, exc_info=True)


def _ensure_webengine():
    """Install PyQt6-WebEngine if no Qt web backend is available.

    Targets the QGIS user-profile dependencies directory so the new
    ``PyQt6.QtWebEngineCore`` merges into the existing PyQt6 namespace
    via ``pkgutil.extend_path``.  A QGIS restart is required afterwards.
    """
    if _has_web_backend():
        _mark_webengine_checked()
        return True
    if _webengine_checked():
        return False

    py = _python_executable()
    if not py:
        logger.warning("Cannot install PyQt6-WebEngine: no Python executable")
        _mark_webengine_checked()
        return False

    os.makedirs(_DEPS_PATH, exist_ok=True)

    try:
        ver = importlib.metadata.version("PyQt6")
        mm = ".".join(ver.split(".")[:2])
        specs = [f"PyQt6-WebEngine~={mm}.0", f"PyQt6-WebEngine-Qt6~={mm}.0"]
    except Exception:
        specs = ["PyQt6-WebEngine", "PyQt6-WebEngine-Qt6"]

    try:
        subprocess.run(  # nosec B603
            [py, "-m", "pip", "install", "--target", _DEPS_PATH, "--no-deps",
             *specs, "--no-warn-script-location"],
            check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=_NO_WINDOW,
            env=_subprocess_env(),
        )
        logger.info(
            "Installed PyQt6-WebEngine into %s — restart QGIS to enable"
            " embedded charts",
            _DEPS_PATH,
        )
        _mark_webengine_checked()
        return True
    except Exception:
        logger.warning("Failed to install PyQt6-WebEngine", exc_info=True)
        _mark_webengine_checked()
        return False


class ExtlibsDownloader(QThread):
    download_done = pyqtSignal(bool, str)  # success, message

    def run(self):
        try:
            if bundle_complete():
                self._finish_ok()
                return
            # Fast path: the heavy prebuilt bundle is already present FOR THIS
            # interpreter and only the light top-up deps (e.g. the ClimaPlots
            # climate stack a stale zip predates) are missing. Skip re-downloading
            # ~85 MB and just pip the gap. Gated on the interpreter tag so an
            # interpreter upgrade (cp312 -> cp313) still re-fetches the bundle:
            # the existing compiled .pyd would be ABI-wrong and presence alone
            # can't detect that. _missing_pip_specs() returns a list here; None
            # means a core package is absent, so we need the full bundle below.
            ready_tag = _read_ready_tag() or ""
            same_interpreter = ready_tag.split("|", 1)[0] == current_tag()
            if same_interpreter and _missing_pip_specs() is not None:
                self._try_pip()
                if bundle_complete():
                    self._finish_ok()
                    return
            # Step 1: fetch the prebuilt bundle (the ABI-locked compiled deps).
            self._try_tagged_zip()
            if bundle_complete():
                self._finish_ok()
                return
            # Step 2: the zip was unavailable for this tag, or it predates a
            # dependency added to requirements.txt. Fill the gaps with pip.
            self._try_pip()
            if bundle_complete():
                self._finish_ok()
                return
            self.download_done.emit(
                False,
                "Could not provision dependencies automatically for "
                f"{current_tag()}. Install the packages from requirements.txt "
                "in the QGIS Python environment manually.")
        except Exception as e:
            self.download_done.emit(False, str(e))

    # -- step 1: tagged prebuilt zip ------------------------------------
    def _try_tagged_zip(self) -> bool:
        return any(self._try_zip(tag) for tag in _bundle_tags())

    def _try_zip(self, tag) -> bool:
        url = BASE_URL + f"extlibs-{tag}.zip"
        if not url.startswith("https://"):
            return False
        zip_path = os.path.join(_PLUGIN_DIR, "_extlibs_dl.zip")
        try:
            with urllib.request.urlopen(url, timeout=120) as resp, open(zip_path, "wb") as f:  # nosec B310
                f.write(resp.read())
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                if names and names[0].startswith("extlibs/"):
                    zf.extractall(_PLUGIN_DIR)
                else:
                    os.makedirs(EXTLIBS_PATH, exist_ok=True)
                    zf.extractall(EXTLIBS_PATH)
            return True
        except Exception:
            return False
        finally:
            if os.path.exists(zip_path):
                try:
                    os.remove(zip_path)
                except OSError:
                    pass

    # -- step 2: runtime pip into extlibs/ ------------------------------
    def _try_pip(self) -> bool:
        py = _python_executable()
        if not py or not os.path.exists(_REQUIREMENTS):
            return False
        os.makedirs(EXTLIBS_PATH, exist_ok=True)
        # Top up only the packages still missing (e.g. the small climate stack a
        # stale prebuilt bundle lacks) rather than reinstalling the whole, heavy
        # requirements set on every launch. Fall back to the full set only when
        # a core package (or its pip name) is unknown/absent.
        specs = _missing_pip_specs()
        install_args = specs if specs else ["-r", _REQUIREMENTS]
        try:
            subprocess.run(  # nosec B603
                [py, "-m", "pip", "install", "--target", EXTLIBS_PATH,
                 *install_args, "--no-warn-script-location"],
                check=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=_NO_WINDOW,
                env=_subprocess_env(),
            )
        except Exception:
            return False
        _strip_qgis_provided(EXTLIBS_PATH)
        _patch_climdex()
        return True

    def _finish_ok(self):
        os.makedirs(EXTLIBS_PATH, exist_ok=True)
        with open(_SENTINEL, "w", encoding="utf-8") as f:
            f.write(_expected_sentinel())
        ensure_on_path()
        _ensure_webengine()
        self.download_done.emit(True, "")
