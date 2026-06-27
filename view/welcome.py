# -*- coding: utf-8 -*-
"""
Welcome / landing page for the FARM tools dialog.

The landing page is a *module hub*: a responsive grid of cards, one per tool.
Each card shows an icon, the module name and a one-line description, and is a
single clickable button that navigates straight to that module's page. The user
lands here and immediately sees every available tool as an interactive grid
(no wall of text). Navigation targets reuse the dialog's ``show_*_page`` /
``_nav_to_*`` methods, so ``farm_tools_dialog.py`` need not know about this file.
"""

from qgis.PyQt.QtCore import (
    QCoreApplication,
    QPoint,
    QRect,
    QRectF,
    QSize,
    Qt,
)
from qgis.PyQt.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from qgis.PyQt.QtSvg import QSvgRenderer
from qgis.PyQt.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import os

from . import module_prefs
from .styles import STYLE_BTN_SECONDARY


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


FARM_GREEN = "#1b6b39"

# Plugin assets/ dir (welcome.py lives in view/, so go up one level).
_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")

# Module kinds that carry their own brand logo (SVG) instead of a drawn line
# icon. Keyed by the same ``kind`` as ``_MODULES``.
_LOGO_SVGS = {
    "optical": "ravi.svg",
    "climaplots": "climaplots.svg",
    "radar": "sentinel1.svg",
    "fieldguide": "fieldguide.svg",
    "download": "easydem.svg",
}


def _svg_pixmap(filename: str, size: int) -> QPixmap:
    """Render an assets/ SVG to a transparent square QPixmap of ``size`` px.
    Returns an empty (transparent) pixmap if the file is missing/invalid, so a
    bad asset degrades to a blank tile rather than crashing the hub."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(os.path.join(_ASSETS_DIR, filename))
    if renderer.isValid():
        # Keep aspect ratio: the trimmed logos are not square, so render into a
        # centred sub-rect instead of stretching to fill the tile.
        bounds = renderer.defaultSize()
        bounds.scale(size, size, Qt.AspectRatioMode.KeepAspectRatio)
        target = QRectF(
            (size - bounds.width()) / 2,
            (size - bounds.height()) / 2,
            bounds.width(),
            bounds.height(),
        )
        painter = QPainter(pix)
        renderer.render(painter, target)
        painter.end()
    return pix

# External links (mirrors ui/intro.html).
_URL_CAIO = "https://www.linkedin.com/in/caioarantes/"
_URL_LUCAS = "https://www.linkedin.com/in/lucas-rios-do-amaral-bb302449/"
_URL_FARM = "https://farmanalytica.com.br"
_URL_SITE = "https://www.farmtools.com.br"
_URL_MATEUS = "https://www.linkedin.com/in/mateuspinto/"
_URL_AGRIGEE = "https://github.com/mateuspinto/AgriGEE.lite"
_LINK_STYLE = "color:#1b6b39; font-weight:bold; text-decoration:none;"

# One entry per module card: (icon kind, name, one-line description, dialog nav
# method, gee_free). ``kind`` reuses the sidebar's icon vocabulary; ``nav_attr``
# is looked up on the dialog at click time so this list is the single source of
# truth. ``gee_free`` flags modules that work without a Google Earth Engine
# sign-in (NASA POWER / local-raster sources) so first-time users can start there.
_MODULES = [
    ("optical", "RAVI (Sentinel-2)",
     "Per-date vegetation-index time series (NDVI, EVI, NDRE…) with cloud masking",
     "show_optical_page", False),
    ("landsat", "Multi-Satellite",
     "Pan-sharpened 15 m Landsat 7/8/9 imagery and multi-mission index series",
     "show_landsat_page", False),
    ("sysi", "SYSI — Synthetic Soil Image",
     "Bare-soil reflectance composite (GEOS3) from cloud-free pixels for soil mapping",
     "show_sysi_page", False),
    ("radar", "Radar (SAR) data",
     "Sentinel-1 VV/VH backscatter time series — cloud-independent monitoring",
     "show_radar_page", False),
    ("download", "EasyDEM",
     "Fetch terrain elevation models (SRTM, Copernicus…) clipped to your area",
     "_nav_to_dem", False),
    ("climaplots", "ClimaPlots",
     "Climate trends, indices and thermo diagrams from NASA POWER daily data",
     "show_climaplots_page", True),
    ("fieldguide", "Field Guide",
     "Per-feature and per-point analysis with adjustable buffer and value extraction",
     "show_fieldguide_page", True),
    ("mapbiomas", "MapBiomas",
     "Brazilian land-use/land-cover by year plus pasture-to-crop transition mapping",
     "show_mapbiomas_page", False),
    ("auth", "GEE Configuration",
     "Connect to Google Earth Engine — sign in and set your project ID",
     "show_auth_page", False),
]


def _ordered_visible_modules():
    """``_MODULES`` entries in the user's order with hidden ones removed.

    Auth is not manageable (pinned), so it is always present and kept last —
    the same position it has occupied on the hub. Mirrors the sidebar rail via
    the shared :mod:`module_prefs`.
    """
    by_key = {entry[0]: entry for entry in _MODULES}
    hidden = module_prefs.get_hidden()
    ordered = []
    for key in module_prefs.get_order():
        if key in hidden:
            continue
        entry = by_key.get(key)
        if entry is not None:
            ordered.append(entry)
    if "auth" in by_key and visible_set_needs_auth():
        ordered.append(by_key["auth"])
    return ordered


def visible_set_needs_auth():
    """True if any visible (non-auth) module requires a GEE sign-in.

    Single-module no-login builds (e.g. ClimaPlots, Field Guide) then drop the
    GEE Configuration entry entirely — there is nothing to sign in for. The
    sidebar rail consults this too, so both surfaces agree.
    """
    by_key = {entry[0]: entry for entry in _MODULES}
    hidden = module_prefs.get_hidden()
    for key in module_prefs.get_order():
        if key in hidden:
            continue
        entry = by_key.get(key)
        if entry is not None and entry[4] is False:  # gee_free is False
            return True
    return False


def _ordered_hidden_modules():
    """``_MODULES`` entries that are currently hidden, in canonical order.

    Powers the hub's "More FARM tools" teaser strip: these modules ship in the
    same plugin and are one click from activation, so they are surfaced (greyed,
    non-navigating) instead of vanishing. Auth is never hideable, so never here.
    """
    by_key = {entry[0]: entry for entry in _MODULES}
    hidden = module_prefs.get_hidden()
    ordered = []
    for key in module_prefs.get_order():
        if key not in hidden:
            continue
        entry = by_key.get(key)
        if entry is not None:
            ordered.append(entry)
    return ordered


class FlowLayout(QLayout):
    """Left-to-right layout that wraps items to the next row when out of width.

    Qt ships no flow layout; this is the canonical subclass (adapted from the Qt
    examples). It gives the card grid its responsive column count for free — the
    number of columns follows the available width.
    """

    def __init__(self, parent=None, margin=0, spacing=16):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items = []

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        if not self._items:
            return QSize()
        w0 = self._items[0].widget()
        margins = self.contentsMargins()
        if w0 is not None:
            min_w = w0.minimumWidth() or w0.sizeHint().width()
            card_h = w0.minimumHeight() or w0.sizeHint().height()
        else:
            hint = self._items[0].sizeHint()
            min_w, card_h = hint.width(), hint.height()
        return QSize(
            min_w + margins.left() + margins.right(),
            card_h + margins.top() + margins.bottom(),
        )

    def _do_layout(self, rect, test_only):
        margins = self.contentsMargins()
        effective = rect.adjusted(
            margins.left(), margins.top(), -margins.right(), -margins.bottom()
        )
        available_w = effective.width()
        spacing = self.spacing()

        if not self._items:
            return margins.top() + margins.bottom()

        # Access the underlying widget to read the card dimensions set via
        # setMinimumWidth / setFixedHeight — QLayoutItem has no minimumWidth().
        w0 = self._items[0].widget()
        if w0 is not None:
            min_w = w0.minimumWidth() or w0.sizeHint().width() or 1
            card_h = w0.minimumHeight() or w0.sizeHint().height() or 1
        else:
            hint = self._items[0].sizeHint()
            min_w = hint.width() or 1
            card_h = hint.height() or 1

        # Column count from minimum card width; then stretch cards to fill row.
        n_cols = max(1, (available_w + spacing) // (min_w + spacing))
        card_w = max(min_w, (available_w - (n_cols - 1) * spacing) // n_cols)

        for i, item in enumerate(self._items):
            col = i % n_cols
            row = i // n_cols
            x = effective.x() + col * (card_w + spacing)
            y = effective.y() + row * (card_h + spacing)
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), QSize(card_w, card_h)))

        n_rows = (len(self._items) + n_cols - 1) // n_cols
        return (
            effective.y()
            + n_rows * card_h
            + (n_rows - 1) * spacing
            - rect.y()
            + margins.bottom()
        )


class _HeightForWidthWidget(QWidget):
    """QWidget that forwards its layout's height-for-width to its container.

    A plain QWidget does NOT advertise a height-for-width layout to the parent
    layout / enclosing QScrollArea, so a ``FlowLayout`` grid's true multi-row
    height is under-reported (as a single row). That makes the scroll area
    mis-decide whether a vertical scrollbar is needed; the scrollbar toggling
    steals ~15 px of width right at the 2-vs-3-column boundary, so the grid
    intermittently sticks at two columns when a third would fit. Forwarding
    height-for-width lets the scroll area size the content correctly, so the
    column count is stable.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        policy = self.sizePolicy()
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        layout = self.layout()
        if layout is not None:
            return layout.heightForWidth(width)
        return super().heightForWidth(width)


def _draw_module_icon(kind: str, color: str, size: int = 30) -> QPixmap:
    """Render a crisp line icon for ``kind`` at ``size`` px.

    Recipes mirror ``Sidebar._draw_icon`` (drawn in a 20-unit space) so a card's
    icon matches its sidebar button; the painter is scaled to ``size``.
    """
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 20.0, size / 20.0)

    pen = QPen(QColor(color), 1.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

    if kind == "auth":
        # Key — sign-in / Earth Engine configuration.
        painter.setPen(pen)
        painter.drawEllipse(QPoint(7, 8), 4, 4)
        painter.drawLine(10, 11, 17, 18)
        painter.drawLine(14, 15, 16, 13)
    elif kind == "optical":
        painter.setPen(pen)
        path = QPainterPath()
        path.moveTo(4, 16)
        path.cubicTo(5, 7, 11, 4, 16, 4)
        path.cubicTo(16, 11, 13, 16, 4, 16)
        painter.drawPath(path)
        painter.drawLine(6, 14, 15, 5)
    elif kind == "sysi":
        painter.setPen(pen)
        painter.drawLine(3, 11, 17, 11)
        painter.drawLine(3, 14, 17, 14)
        painter.drawLine(3, 17, 17, 17)
        painter.drawLine(10, 8, 10, 3)
        painter.drawLine(10, 6, 7, 4)
        painter.drawLine(10, 6, 13, 4)
    elif kind == "radar":
        painter.setPen(pen)
        painter.drawArc(QRect(2, 2, 14, 14), 0 * 16, 90 * 16)
        painter.drawArc(QRect(4, 4, 10, 10), 0 * 16, 90 * 16)
        painter.drawArc(QRect(6, 6, 6, 6), 0 * 16, 90 * 16)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawEllipse(QPoint(9, 9), 1, 1)
    elif kind == "landsat":
        painter.setPen(pen)
        painter.drawRect(QRect(3, 3, 8, 8))
        painter.drawLine(7, 3, 7, 11)
        painter.drawLine(3, 7, 11, 7)
        painter.drawArc(QRect(10, 10, 6, 6), 0, 360 * 16)
        painter.drawLine(15, 15, 18, 18)
    elif kind == "fieldguide":
        painter.setPen(pen)
        painter.drawEllipse(QPoint(10, 8), 4, 4)
        painter.drawLine(6, 11, 10, 17)
        painter.drawLine(14, 11, 10, 17)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawEllipse(QPoint(10, 8), 1, 1)
    elif kind == "climaplots":
        painter.setPen(pen)
        painter.drawEllipse(QPoint(7, 7), 3, 3)
        painter.drawLine(7, 1, 7, 3)
        painter.drawLine(1, 7, 3, 7)
        painter.drawLine(3, 3, 4, 4)
        painter.drawLine(11, 3, 10, 4)
        painter.drawLine(3, 11, 4, 10)
        drop = QPainterPath()
        drop.moveTo(13.5, 9.5)
        drop.cubicTo(11.0, 13.0, 11.0, 15.0, 13.5, 17.0)
        drop.cubicTo(16.0, 15.0, 16.0, 13.0, 13.5, 9.5)
        painter.drawPath(drop)
    elif kind == "mapbiomas":
        # Land-cover mosaic — a map tile split into patches, one filled.
        painter.setPen(pen)
        painter.drawRect(QRect(3, 4, 14, 12))
        painter.drawLine(9, 4, 9, 16)
        painter.drawLine(3, 10, 17, 10)
        edge = QPainterPath()
        edge.moveTo(9, 7)
        edge.cubicTo(12, 7.5, 11, 9.5, 14, 10)
        painter.drawPath(edge)
        painter.fillRect(QRect(4, 11, 4, 4), QColor(color))
    else:
        painter.setPen(pen)
        painter.drawLine(10, 3, 10, 12)
        painter.drawLine(6, 9, 10, 13)
        painter.drawLine(14, 9, 10, 13)
        painter.drawLine(5, 16, 15, 16)

    painter.end()
    return pix


_CARD_WIDTH = 248
# Tall enough for a one-line title plus a four-line wrapped description.
_CARD_HEIGHT = 116


def _build_module_card(dialog, kind, name, desc, nav_attr, gee_free=False):
    """One clickable card. The whole card is a button that navigates on click."""
    card = QPushButton()
    card.setObjectName("moduleCard")
    card.setCursor(Qt.CursorShape.PointingHandCursor)
    card.setMinimumWidth(_CARD_WIDTH)
    card.setFixedHeight(_CARD_HEIGHT)
    card.setToolTip(_tr(name))
    card.setStyleSheet("""
        QPushButton#moduleCard {
            background-color: #ffffff;
            border: 1px solid #e4e7e5;
            border-radius: 12px;
            text-align: left;
        }
        QPushButton#moduleCard:hover {
            background-color: #f7fbf8;
            border-color: #1b6b39;
        }
        QPushButton#moduleCard:pressed {
            background-color: #eef6f0;
        }
        QPushButton#moduleCard QLabel { background: transparent; border: none; }
        QToolTip {
            background-color: #ffffff;
            color: #1a1a1a;
            border: 1px solid #e0e0e0;
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 11px;
        }
    """)

    # Horizontal: icon tile on the left, text wrapped beside it — keeps each
    # card short so the grid stays compact.
    lay = QHBoxLayout(card)
    lay.setContentsMargins(12, 12, 12, 12)
    lay.setSpacing(11)

    icon_tile = QLabel()
    icon_tile.setFixedSize(36, 36)
    icon_tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
    if kind in _LOGO_SVGS:
        # Brand logo: render bigger to fill the tile, on a neutral white tile so
        # the logo's own colours read cleanly.
        icon_tile.setStyleSheet("background-color: #ffffff; border-radius: 9px;")
        icon_tile.setPixmap(_svg_pixmap(_LOGO_SVGS[kind], 30))
    else:
        icon_tile.setStyleSheet("background-color: #e8f5e9; border-radius: 9px;")
        icon_tile.setPixmap(_draw_module_icon(kind, FARM_GREEN, 20))
    lay.addWidget(icon_tile, 0, Qt.AlignmentFlag.AlignTop)

    text_col = QVBoxLayout()
    text_col.setContentsMargins(0, 0, 0, 0)
    text_col.setSpacing(2)

    title = QLabel(_tr(name))
    title.setStyleSheet("color: #1a1a1a; font-size: 13px; font-weight: bold;")
    title.setWordWrap(True)

    if gee_free:
        # Badge row: title beside a green "No login" pill so first-time users can
        # spot the tools that run without a Google Earth Engine sign-in.
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(6)
        title_row.addWidget(title, 1)
        badge = QLabel(_tr("No login"))
        badge.setToolTip(_tr("Works without a Google Earth Engine sign-in"))
        badge.setStyleSheet(
            "background-color: #e8f5e9; color: #1b6b39; font-size: 9px;"
            " font-weight: bold; border: 1px solid #b7dcc0; border-radius: 7px;"
            " padding: 1px 6px;"
        )
        title_row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        text_col.addLayout(title_row)
    else:
        text_col.addWidget(title)

    blurb = QLabel(_tr(desc))
    blurb.setWordWrap(True)
    blurb.setStyleSheet("color: #6b7280; font-size: 11px; line-height: 1.3;")
    blurb.setAlignment(Qt.AlignmentFlag.AlignTop)
    text_col.addWidget(blurb, 1)

    lay.addLayout(text_col, 1)

    # Resolve the nav method lazily on the dialog so this stays decoupled.
    def _navigate(_checked=False, attr=nav_attr):
        handler = getattr(dialog, attr, None)
        if callable(handler):
            handler()

    card.clicked.connect(_navigate)
    return card


def _build_teaser_card(dialog, kind, name, desc, gee_free=False):
    """A demoted "More tools" card: greyed, shows a ``+ Add`` affordance.

    The module is included in this plugin but hidden. Clicking the card un-hides
    it via :mod:`module_prefs` and triggers ``dialog.refresh_modules()`` so the
    card promotes into the active grid (and the sidebar rail) immediately.
    """
    card = QPushButton()
    card.setObjectName("teaserCard")
    card.setCursor(Qt.CursorShape.PointingHandCursor)
    card.setMinimumWidth(_CARD_WIDTH)
    card.setFixedHeight(_CARD_HEIGHT)
    card.setToolTip(_tr("Add {0} — included in this plugin").format(_tr(name)))
    card.setStyleSheet("""
        QPushButton#teaserCard {
            background-color: #fafafa;
            border: 1px dashed #d4d8d6;
            border-radius: 12px;
            text-align: left;
        }
        QPushButton#teaserCard:hover {
            background-color: #f7fbf8;
            border-color: #1b6b39;
            border-style: solid;
        }
        QPushButton#teaserCard:pressed {
            background-color: #eef6f0;
        }
        QPushButton#teaserCard QLabel { background: transparent; border: none; }
        QToolTip {
            background-color: #ffffff;
            color: #1a1a1a;
            border: 1px solid #e0e0e0;
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 11px;
        }
    """)

    lay = QHBoxLayout(card)
    lay.setContentsMargins(12, 12, 12, 12)
    lay.setSpacing(11)

    icon_tile = QLabel()
    icon_tile.setFixedSize(36, 36)
    icon_tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
    # Greyed icon so the card reads as inactive vs. the colourful active grid.
    icon_tile.setStyleSheet("background-color: #eeeeee; border-radius: 9px;")
    if kind in _LOGO_SVGS:
        icon_tile.setPixmap(_svg_pixmap(_LOGO_SVGS[kind], 30))
    else:
        icon_tile.setPixmap(_draw_module_icon(kind, "#9aa0a6", 20))
    lay.addWidget(icon_tile, 0, Qt.AlignmentFlag.AlignTop)

    text_col = QVBoxLayout()
    text_col.setContentsMargins(0, 0, 0, 0)
    text_col.setSpacing(2)

    title_row = QHBoxLayout()
    title_row.setContentsMargins(0, 0, 0, 0)
    title_row.setSpacing(6)
    title = QLabel(_tr(name))
    title.setStyleSheet("color: #6b7280; font-size: 13px; font-weight: bold;")
    title.setWordWrap(True)
    title_row.addWidget(title, 1)
    add = QLabel(_tr("+ Add"))
    add.setStyleSheet(
        "color: #1b6b39; font-size: 10px; font-weight: bold;"
        " border: 1px solid #b7dcc0; border-radius: 7px; padding: 1px 6px;"
    )
    title_row.addWidget(add, 0, Qt.AlignmentFlag.AlignTop)
    text_col.addLayout(title_row)

    blurb = QLabel(_tr(desc))
    blurb.setWordWrap(True)
    blurb.setStyleSheet("color: #9aa0a6; font-size: 11px; line-height: 1.3;")
    blurb.setAlignment(Qt.AlignmentFlag.AlignTop)
    text_col.addWidget(blurb, 1)

    lay.addLayout(text_col, 1)

    def _activate(_checked=False, key=kind):
        module_prefs.unhide(key)
        refresh = getattr(dialog, "refresh_modules", None)
        if callable(refresh):
            refresh()

    card.clicked.connect(_activate)
    return card


def _build_about_section():
    """About card below the grid: the RAVI/FARM story, collaboration and links."""
    frame = QFrame()
    frame.setObjectName("aboutCard")
    frame.setStyleSheet("""
        QFrame#aboutCard {
            background-color: #ffffff;
            border: 1px solid #e4e7e5;
            border-radius: 12px;
        }
        QFrame#aboutCard QLabel { background: transparent; border: none; }
    """)
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(20, 18, 20, 18)
    lay.setSpacing(10)

    caption = QLabel(_tr("ABOUT"))
    caption.setStyleSheet(
        "color: #1b6b39; font-size: 11px; letter-spacing: 1px; font-weight: bold;"
    )
    lay.addWidget(caption)

    story = QLabel(
        _tr(
            "<b>FARM tools</b> (formerly RAVI — Remote Analysis of Vegetation Indices) "
            "began as the undergraduate thesis of "
            "<a href='{caio}' style='{ls}'>Caio Arantes</a>, supervised by "
            "<a href='{lucas}' style='{ls}'>Prof. Dr. Lucas dos Rios Amaral</a>, "
            "and is now an open-source project maintained with the support of "
            "<a href='{farm}' style='{ls}'>FARM Analytica</a>, co-founded by Caio. "
            "Committed to technology diffusion and the open-source philosophy, it "
            "brings <b>Google Earth Engine</b> processing into QGIS — turning "
            "satellite archives into vegetation, soil, radar and climate insight, "
            "without leaving your map."
        ).format(caio=_URL_CAIO, lucas=_URL_LUCAS, farm=_URL_FARM, ls=_LINK_STYLE)
    )
    story.setWordWrap(True)
    story.setTextFormat(Qt.TextFormat.RichText)
    story.setOpenExternalLinks(True)
    story.setStyleSheet("color: #555555; font-size: 12px; line-height: 1.4;")
    lay.addWidget(story)

    collab = QLabel(
        _tr(
            "🛰️ Landsat super-resolution is built on "
            "<a href='{agrigee}' style='{ls}'>AgriGEE.lite</a>, in collaboration "
            "with its author <a href='{mateus}' style='{ls}'>Mateus Pinto</a>."
        ).format(agrigee=_URL_AGRIGEE, mateus=_URL_MATEUS, ls=_LINK_STYLE)
    )
    collab.setWordWrap(True)
    collab.setTextFormat(Qt.TextFormat.RichText)
    collab.setOpenExternalLinks(True)
    collab.setStyleSheet(
        "color: #1b5e20; font-size: 11px; background: #e8f5e9;"
        " border-radius: 4px; padding: 8px 10px;"
    )
    lay.addWidget(collab)

    footer = QLabel(
        _tr(
            "Learn more and read the setup guide at "
            "<a href='{site}' style='{ls}'>www.farmtools.com.br</a> · "
            "Commercial inquiries: "
            "<a href='{farm}' style='{ls}'>FARM Analytica</a>"
        ).format(site=_URL_SITE, farm=_URL_FARM, ls=_LINK_STYLE)
    )
    footer.setWordWrap(True)
    footer.setTextFormat(Qt.TextFormat.RichText)
    footer.setOpenExternalLinks(True)
    footer.setStyleSheet("color: #9e9e9e; font-size: 11px; padding-top: 4px;")
    lay.addWidget(footer)

    return frame


def _build_folder_section(dialog):
    """Download-folder picker, shared by every module's export action.

    Exposes ``dialog.folder_input``, ``dialog.btn_clear_folder`` and
    ``dialog.btn_browse_folder`` — wired by ``farm_tools.py``.
    """
    frame = QFrame()
    frame.setObjectName("folderCard")
    frame.setStyleSheet("""
        QFrame#folderCard {
            background-color: #ffffff;
            border: 1px solid #e4e7e5;
            border-radius: 12px;
        }
        QFrame#folderCard QLabel { background: transparent; border: none; }
    """)
    folder_lay = QVBoxLayout(frame)
    folder_lay.setContentsMargins(20, 14, 20, 14)
    folder_lay.setSpacing(8)

    folder_lbl = QLabel(_tr("Download folder"))
    folder_lbl.setStyleSheet("color: #616161; font-size: 11px; font-weight: bold;")
    folder_lay.addWidget(folder_lbl)

    folder_input_row = QHBoxLayout()
    folder_input_row.setContentsMargins(0, 0, 0, 0)
    folder_input_row.setSpacing(8)

    dialog.folder_input = QLineEdit()
    dialog.folder_input.setReadOnly(True)
    dialog.folder_input.setPlaceholderText(_tr("System temp (default)"))
    dialog.folder_input.setFixedHeight(28)
    dialog.folder_input.setStyleSheet("""
        QLineEdit {
            background-color: #f5f5f5;
            color: #424242;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 12px;
        }
    """)
    folder_input_row.addWidget(dialog.folder_input, 1)

    dialog.btn_clear_folder = QPushButton("✕")
    dialog.btn_clear_folder.setFixedSize(28, 28)
    dialog.btn_clear_folder.setToolTip(_tr("Clear download folder"))
    dialog.btn_clear_folder.setStyleSheet("""
        QPushButton {
            background-color: transparent;
            color: #bdbdbd;
            border: none;
            border-radius: 4px;
            font-size: 13px;
        }
        QPushButton:hover:enabled {
            color: #c62828;
            background-color: #fdecea;
        }
        QPushButton:disabled { color: #eeeeee; }
    """)
    folder_input_row.addWidget(dialog.btn_clear_folder)

    dialog.btn_browse_folder = QPushButton(_tr("Browse"))
    dialog.btn_browse_folder.setFixedHeight(28)
    dialog.btn_browse_folder.setStyleSheet(STYLE_BTN_SECONDARY)
    folder_input_row.addWidget(dialog.btn_browse_folder)

    folder_lay.addLayout(folder_input_row)

    def _sync_clear_enabled(text):
        dialog.btn_clear_folder.setEnabled(bool(text))

    dialog.folder_input.textChanged.connect(_sync_clear_enabled)
    _sync_clear_enabled(dialog.folder_input.text())

    return frame


def _build_hub_section(dialog):
    """Header strip + responsive grid of module cards."""
    container = _HeightForWidthWidget()
    container.setStyleSheet("background: transparent;")
    outer = QVBoxLayout(container)
    outer.setContentsMargins(4, 4, 4, 4)
    outer.setSpacing(6)

    title_row = QHBoxLayout()
    title_row.setContentsMargins(0, 0, 0, 0)
    title_row.setSpacing(8)
    title = QLabel(_tr("Welcome to FARM tools"))
    title.setStyleSheet("color: #1b6b39; font-size: 20px; font-weight: bold;")
    title_row.addWidget(title)
    title_row.addStretch(1)

    # Mirror of the auth page's sign-in status pill. Kept in sync by
    # ``farm_tools_dialog.set_auth_state``; clicking opens the auth /
    # Earth Engine configuration page (wired in ``farm_tools.py``).
    dialog.welcome_auth_badge = QPushButton(_tr("Checking sign-in status…"))
    dialog.welcome_auth_badge.setCursor(Qt.CursorShape.PointingHandCursor)
    dialog.welcome_auth_badge.setToolTip(
        _tr("Click to open sign-in / Earth Engine configuration")
    )
    dialog.welcome_auth_badge.setFixedHeight(22)
    dialog.welcome_auth_badge.setStyleSheet(
        """
        QPushButton {
            background-color: transparent;
            color: #757575;
            border: none;
            font-size: 11px;
            font-weight: bold;
            padding: 0 10px;
            text-align: center;
        }
        """
    )
    # No-login-only build: nothing to sign in for, so hide the status pill.
    dialog.welcome_auth_badge.setVisible(visible_set_needs_auth())
    title_row.addWidget(dialog.welcome_auth_badge)

    # Opens the Customize-modules dialog (reorder / show-hide). Subtle, secondary
    # link styling so it sits quietly beside the sign-in badge.
    dialog.welcome_customize_btn = QPushButton(_tr("⚙  Customize"))
    dialog.welcome_customize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    dialog.welcome_customize_btn.setToolTip(
        _tr("Reorder, show or hide modules")
    )
    dialog.welcome_customize_btn.setFixedHeight(22)
    dialog.welcome_customize_btn.setStyleSheet(
        """
        QPushButton {
            background-color: transparent;
            color: #757575;
            border: none;
            font-size: 11px;
            font-weight: bold;
            padding: 0 10px;
            text-align: center;
        }
        QPushButton:hover { color: #1b6b39; }
        """
    )
    dialog.welcome_customize_btn.clicked.connect(
        lambda: _open_manage_dialog(dialog)
    )
    title_row.addWidget(dialog.welcome_customize_btn)
    outer.addLayout(title_row)

    subtitle = QLabel(
        _tr("Pick a tool to get started")
    )
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet("color: #6b7280; font-size: 12px;")
    outer.addWidget(subtitle)
    outer.addSpacing(6)

    grid_host = _HeightForWidthWidget()
    grid_host.setStyleSheet("background: transparent;")
    grid = FlowLayout(grid_host, margin=0, spacing=12)
    # Kept on the dialog so rebuild_module_grid() can repopulate after the user
    # reorders or hides modules in the Customize dialog.
    dialog._module_grid = grid
    dialog._module_grid_host = grid_host
    for kind, name, desc, nav_attr, gee_free in _ordered_visible_modules():
        grid.addWidget(
            _build_module_card(dialog, kind, name, desc, nav_attr, gee_free))
    outer.addWidget(grid_host)

    outer.addWidget(_build_teaser_section(dialog))

    outer.addSpacing(16)
    outer.addWidget(_build_folder_section(dialog))
    outer.addSpacing(16)
    outer.addWidget(_build_about_section())
    outer.addStretch(1)

    return container


def _open_manage_dialog(dialog):
    """Open the Customize-modules dialog; rebuild both surfaces on Done.

    Imported lazily to avoid a circular import (manage_modules imports helpers
    from this module)."""
    from .manage_modules import ManageModulesDialog

    refresh = getattr(dialog, "refresh_modules", None)
    dlg = ManageModulesDialog(dialog, on_apply=refresh)
    dlg.exec()


def _build_teaser_section(dialog):
    """"More FARM tools" strip: greyed teaser cards for hidden-but-included modules.

    Hidden entirely (header + grid) when nothing is hidden — a full build shows
    no strip. ``_populate_teaser_grid`` fills it and toggles the section's
    visibility, and is re-run by ``rebuild_module_grid`` after every prefs change.
    """
    section = _HeightForWidthWidget()
    section.setStyleSheet("background: transparent;")
    lay = QVBoxLayout(section)
    lay.setContentsMargins(0, 16, 0, 0)
    lay.setSpacing(6)

    header = QLabel(_tr("More FARM tools"))
    header.setStyleSheet(
        "color: #1b6b39; font-size: 13px; font-weight: bold;"
    )
    lay.addWidget(header)

    sub = QLabel(
        _tr("Included in this plugin — click to add to your workspace.")
    )
    sub.setWordWrap(True)
    sub.setStyleSheet("color: #9aa0a6; font-size: 11px;")
    lay.addWidget(sub)
    lay.addSpacing(4)

    grid_host = _HeightForWidthWidget()
    grid_host.setStyleSheet("background: transparent;")
    grid = FlowLayout(grid_host, margin=0, spacing=12)
    lay.addWidget(grid_host)

    dialog._teaser_section = section
    dialog._teaser_grid = grid
    dialog._teaser_grid_host = grid_host
    _populate_teaser_grid(dialog)
    return section


def _populate_teaser_grid(dialog):
    """(Re)fill the teaser grid; hide the whole section when nothing is hidden."""
    grid = getattr(dialog, "_teaser_grid", None)
    section = getattr(dialog, "_teaser_section", None)
    if grid is None or section is None:
        return
    while grid.count():
        item = grid.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
    hidden = _ordered_hidden_modules()
    for kind, name, desc, _nav_attr, gee_free in hidden:
        grid.addWidget(_build_teaser_card(dialog, kind, name, desc, gee_free))
    grid.invalidate()
    section.setVisible(bool(hidden))
    host = getattr(dialog, "_teaser_grid_host", None)
    if host is not None:
        host.updateGeometry()


def rebuild_module_grid(dialog):
    """Repopulate the hub grid from current prefs (after a Customize change)."""
    grid = getattr(dialog, "_module_grid", None)
    if grid is None:
        return
    # Drop the existing cards, then re-add in the new order / visibility.
    while grid.count():
        item = grid.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
    for kind, name, desc, nav_attr, gee_free in _ordered_visible_modules():
        grid.addWidget(
            _build_module_card(dialog, kind, name, desc, nav_attr, gee_free))
    grid.invalidate()
    host = getattr(dialog, "_module_grid_host", None)
    if host is not None:
        host.updateGeometry()
    # Keep the teaser strip in sync — modules just hidden/shown move between grids.
    _populate_teaser_grid(dialog)
    # Re-toggle the header sign-in pill: hiding/showing modules can flip whether
    # any visible module still needs a GEE login.
    badge = getattr(dialog, "welcome_auth_badge", None)
    if badge is not None:
        badge.setVisible(visible_set_needs_auth())


def setup_welcome_page(dialog, page):
    """Populate the landing page with the scrollable module hub grid."""
    page.setStyleSheet("background-color: #f5f5f5;")

    page_lay = QVBoxLayout(page)
    page_lay.setContentsMargins(20, 20, 20, 4)
    page_lay.setSpacing(0)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
    scroll.setWidget(_build_hub_section(dialog))
    page_lay.addWidget(scroll, 1)
