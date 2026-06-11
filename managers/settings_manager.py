# -*- coding: utf-8 -*-
"""
Settings management module.

Handles persistence of user preferences and plugin settings in QGIS.
"""

from qgis.core import QgsSettings


class SettingsManager:
    """Manages plugin settings and user preferences in QGIS."""

    SETTINGS_PREFIX = "qgis-RAVI/"
    DOWNLOAD_FOLDER_KEY = SETTINGS_PREFIX + "dem_download_folder"
    PROXY_KEY = SETTINGS_PREFIX + "proxy"

    @staticmethod
    def save_download_folder(folder_path: str) -> None:

        settings = QgsSettings()
        settings.setValue(SettingsManager.DOWNLOAD_FOLDER_KEY, folder_path)

    @staticmethod
    def clear_download_folder() -> None:

        settings = QgsSettings()
        settings.remove(SettingsManager.DOWNLOAD_FOLDER_KEY)

    @staticmethod
    def load_download_folder() -> str:

        settings = QgsSettings()
        return settings.value(SettingsManager.DOWNLOAD_FOLDER_KEY, "", type=str)

    @staticmethod
    def get_proxy() -> str:
        """Optional HTTP(S) proxy URL for outbound API calls (e.g. NASA POWER)."""
        settings = QgsSettings()
        return settings.value(SettingsManager.PROXY_KEY, "", type=str)

    @staticmethod
    def set_proxy(proxy: str) -> None:
        settings = QgsSettings()
        settings.setValue(SettingsManager.PROXY_KEY, proxy or "")
