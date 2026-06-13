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

from qgis.PyQt.QtGui import QDesktopServices

try:
    from qgis.PyQt.QtWebKitWidgets import QWebPage, QWebView

    USING_WEBENGINE = False
except ImportError:  # Qt6 / QGIS 4: WebKit is gone, use WebEngine
    from qgis.PyQt.QtWebEngineCore import QWebEnginePage
    from qgis.PyQt.QtWebEngineWidgets import QWebEngineView as QWebView

    USING_WEBENGINE = True


if USING_WEBENGINE:

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
    if USING_WEBENGINE:
        view.setPage(_ExternalLinkPage(view))
    else:
        view.page().setLinkDelegationPolicy(QWebPage.DelegateAllLinks)
        view.linkClicked.connect(QDesktopServices.openUrl)
