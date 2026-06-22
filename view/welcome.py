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
    QSize,
    Qt,
)
from qgis.PyQt.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
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

from .styles import STYLE_BTN_SECONDARY


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


FARM_GREEN = "#1b6b39"

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
    icon_tile.setStyleSheet(
        "background-color: #e8f5e9; border-radius: 9px;"
    )
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
    title_row.addWidget(dialog.welcome_auth_badge)
    outer.addLayout(title_row)

    subtitle = QLabel(
        _tr("Pick a tool to get started — bring Google Earth Engine into QGIS.")
    )
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet("color: #6b7280; font-size: 12px;")
    outer.addWidget(subtitle)
    outer.addSpacing(6)

    grid_host = _HeightForWidthWidget()
    grid_host.setStyleSheet("background: transparent;")
    grid = FlowLayout(grid_host, margin=0, spacing=12)
    for kind, name, desc, nav_attr, gee_free in _MODULES:
        grid.addWidget(
            _build_module_card(dialog, kind, name, desc, nav_attr, gee_free))
    outer.addWidget(grid_host)
    outer.addSpacing(16)
    outer.addWidget(_build_folder_section(dialog))
    outer.addSpacing(16)
    outer.addWidget(_build_about_section())
    outer.addStretch(1)

    return container


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
