# -*- coding: utf-8 -*-
"""
QGIS-tier test: round-trips SettingsManager against a real QgsSettings.

Run under a QGIS Python (qgis.core importable). Skipped automatically in the
headless unit tier. Uses an isolated in-memory settings scope so the developer's
real QGIS profile is never touched.
"""

import pytest

pytestmark = pytest.mark.qgis


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path):
    """Point QSettings at a throwaway ini file for the duration of the test."""
    from qgis.PyQt.QtCore import QSettings

    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(
        QSettings.IniFormat, QSettings.UserScope, str(tmp_path)
    )
    yield


def test_download_folder_round_trip():
    from farm_tools.managers.settings_manager import SettingsManager

    SettingsManager.save_download_folder("/tmp/dem")
    assert SettingsManager.load_download_folder() == "/tmp/dem"

    SettingsManager.clear_download_folder()
    assert SettingsManager.load_download_folder() == ""


def test_proxy_default_is_empty_string():
    from farm_tools.managers.settings_manager import SettingsManager

    assert SettingsManager.get_proxy() == ""


def test_settings_keys_are_namespaced():
    from farm_tools.managers.settings_manager import SettingsManager

    assert SettingsManager.DOWNLOAD_FOLDER_KEY.startswith("qgis-RAVI/")
    assert SettingsManager.PROXY_KEY.startswith("qgis-RAVI/")
