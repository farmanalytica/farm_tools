# -*- coding: utf-8 -*-
"""
Qt5/Qt6 web view compatibility layer.

QGIS 3.x Windows builds ship only QtWebKit, while QGIS 4 (Qt6) ships only
QtWebEngine. View code imports ``QWebView`` from here instead of from either
backend; on Qt6 the name is an alias for ``QWebEngineView``. Both backends
support the only view APIs the plugin uses: ``setHtml()`` and ``load(QUrl)``.

``delegate_external_links()`` wraps the one backend-specific behaviour we
need: opening clicked links in the system browser (WebKit uses link
delegation, WebEngine needs a custom page that intercepts navigation).
"""

import logging
import os
import sys

from qgis.PyQt.QtGui import QDesktopServices

logger = logging.getLogger(__name__)

# Re-exported for view code: the whole point of this module.
__all__ = [
    "QWebView",
    "USING_WEBENGINE",
    "HAS_WEB_BACKEND",
    "delegate_external_links",
]

try:
    from qgis.PyQt.QtWebKitWidgets import QWebPage, QWebView

    USING_WEBENGINE = False
    HAS_WEB_BACKEND = True
except ImportError:  # Qt6 / QGIS 4: WebKit is gone, try WebEngine
    try:
        # QGIS 4.0.x Windows packaging ships QtWebEngine without the ANGLE GL
        # runtime (libEGL.dll / libGLESv2.dll), so every
        # QtWebEngineProcess.exe child dies at startup with
        # STATUS_DLL_NOT_FOUND (0xC0000135). Running Chromium in-process
        # sidesteps the broken helper. The flag must be in the environment
        # before WebEngine initializes, and it is process-wide, so gate it on
        # the ANGLE DLL actually being absent.
        if sys.platform == "win32":
            try:
                from qgis.PyQt.QtCore import QLibraryInfo

                _exe_dir = QLibraryInfo.path(
                    QLibraryInfo.LibraryPath.LibraryExecutablesPath
                )
                if not os.path.isfile(os.path.join(_exe_dir, "libGLESv2.dll")):
                    _flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
                    if "--single-process" not in _flags:
                        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
                            _flags + " --single-process"
                        ).strip()
            except Exception:
                logger.debug(
                    "Failed to set QTWEBENGINE_CHROMIUM_FLAGS single-process"
                    " ANGLE workaround",
                    exc_info=True,
                )

        from qgis.PyQt.QtWebEngineCore import QWebEnginePage
        from qgis.PyQt.QtWebEngineWidgets import QWebEngineView as QWebView

        USING_WEBENGINE = True
        HAS_WEB_BACKEND = True
    except ImportError:
        # Neither QtWebKit nor QtWebEngine available (e.g. macOS QGIS 4
        # without the WebEngine Python bindings). Provide a stub so the
        # plugin can still load; chart features degrade to "open in browser".
        from qgis.PyQt.QtCore import Qt, pyqtSignal
        from qgis.PyQt.QtWidgets import QLabel

        logger.warning(
            "Neither QtWebKit nor QtWebEngine found — "
            "in-plugin chart views will be unavailable"
        )

        class QWebView(QLabel):
            """Placeholder widget when no web backend is installed."""

            loadFinished = pyqtSignal(bool)

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.setWordWrap(True)
                self.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setText(
                    "Embedded charts unavailable.\n"
                    "Restart QGIS or use 'Open in browser'."
                )

            def setHtml(self, html, base_url=None):
                pass

            def load(self, url):
                pass

            def page(self):
                return None

        USING_WEBENGINE = False
        HAS_WEB_BACKEND = False


if HAS_WEB_BACKEND and USING_WEBENGINE:

    class _ExternalLinkPage(QWebEnginePage):
        """Open clicked http(s) links in the system browser instead of in-view."""

        def acceptNavigationRequest(self, url, nav_type, is_main_frame):
            if (
                nav_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked
                and url.scheme() in ("http", "https")
            ):
                QDesktopServices.openUrl(url)
                return False
            return super().acceptNavigationRequest(url, nav_type, is_main_frame)


def delegate_external_links(view):
    """Make links clicked inside ``view`` open in the system browser."""
    if not HAS_WEB_BACKEND:
        return
    if USING_WEBENGINE:
        view.setPage(_ExternalLinkPage(view))
    else:
        view.page().setLinkDelegationPolicy(QWebPage.DelegateAllLinks)
        view.linkClicked.connect(QDesktopServices.openUrl)
