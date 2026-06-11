# -*- coding: utf-8 -*-
"""
Shared pytest fixtures + headless bootstrap for the RAVI test suite.

Two tiers:
  * unit  — runs in any Python. ``ee`` / ``qgis`` / ``shapely`` are replaced
            with lightweight stubs when the real packages are absent, so pure
            logic can be imported and exercised without QGIS.
  * qgis  — runs under a real QGIS Python (``qgis.core`` importable). Tests
            marked ``@pytest.mark.qgis`` are skipped automatically otherwise.

The plugin is registered under the import name ``farm_tools`` so the
package-relative imports (``from ..services...``) resolve. Importing it here
does NOT execute ``__init__.py`` (that pulls in Qt) — it is registered as a
namespace package pointing at the plugin dir.
"""

import sys
import types
import pathlib
from unittest.mock import MagicMock

import pytest

PLUGIN_DIR = pathlib.Path(__file__).resolve().parent.parent
PKG = "farm_tools"


# --------------------------------------------------------------------------- #
# Make the plugin importable as a package without running __init__.py
# --------------------------------------------------------------------------- #
def _register_package():
    if PKG in sys.modules:
        return
    pkg = types.ModuleType(PKG)
    pkg.__path__ = [str(PLUGIN_DIR)]  # namespace package -> submodules resolve
    sys.modules[PKG] = pkg


# --------------------------------------------------------------------------- #
# Dependency detection
# --------------------------------------------------------------------------- #
def _importable(name):
    try:
        __import__(name)
        return True
    except Exception:
        return False


HAS_QGIS = _importable("qgis.core")
HAS_EE = _importable("ee")


# --------------------------------------------------------------------------- #
# Stubs (installed only when the real dependency is missing)
# --------------------------------------------------------------------------- #
class _AutoModule(types.ModuleType):
    """Module whose every missing attribute is a fresh MagicMock."""

    def __getattr__(self, name):
        m = MagicMock(name=f"{self.__name__}.{name}")
        setattr(self, name, m)
        return m


def _install_ee_stub():
    """Minimal ``ee`` stub.

    Real classes for the few names used in ``isinstance`` checks; everything
    else is a MagicMock so call-composition tests can assert on chained calls.
    """
    ee = _AutoModule("ee")

    class Geometry:  # used in dem_registry isinstance()
        def __init__(self, *a, **k):
            self._args = a

    class Image:
        def __init__(self, *a, **k):
            self._args = a

    class Feature:
        def __init__(self, *a, **k):
            self._args = a

    class FeatureCollection:
        def __init__(self, *a, **k):
            self._args = a

    ee.Geometry = Geometry
    ee.Image = Image
    ee.Feature = Feature
    ee.FeatureCollection = FeatureCollection
    sys.modules["ee"] = ee


def _install_qgis_stub():
    """Stub the qgis namespace + the PyQt submodules the plugin imports."""
    for name in (
        "qgis",
        "qgis.core",
        "qgis.gui",
        "qgis.utils",
        "qgis.PyQt",
        "qgis.PyQt.QtCore",
        "qgis.PyQt.QtGui",
        "qgis.PyQt.QtWidgets",
    ):
        if name not in sys.modules:
            sys.modules[name] = _AutoModule(name)


def _install_misc_stubs():
    if not _importable("shapely"):
        sys.modules["shapely"] = _AutoModule("shapely")
        sys.modules["shapely.geometry"] = _AutoModule("shapely.geometry")


# --------------------------------------------------------------------------- #
# Session bootstrap
# --------------------------------------------------------------------------- #
def pytest_configure(config):
    _register_package()
    if not HAS_EE:
        _install_ee_stub()
    if not HAS_QGIS:
        _install_qgis_stub()
    _install_misc_stubs()


def pytest_collection_modifyitems(config, items):
    """Skip qgis-marked tests when no real QGIS interpreter is present."""
    if HAS_QGIS:
        return
    skip = pytest.mark.skip(reason="needs a real QGIS Python (qgis.core absent)")
    for item in items:
        if "qgis" in item.keywords:
            item.add_marker(skip)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def ee_image():
    """A MagicMock standing in for an ``ee.Image``.

    Chained calls (``.select(...).divide(...)``) each return a fresh MagicMock,
    so tests assert on the call graph an index function builds.
    """
    return MagicMock(name="ee.Image")


@pytest.fixture
def has_qgis():
    return HAS_QGIS
