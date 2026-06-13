# -*- coding: utf-8 -*-
"""
Welcome / landing page for the FARM tools dialog.

Holds the project story and the feature overview that used to live in the
left column of the Auth page. The dialog opens here; the user proceeds to
the Auth page via the "Get started" button, or returns any time by clicking
the FARM tools brand at the top of the sidebar.
"""

from qgis.PyQt.QtCore import Qt, QCoreApplication
from qgis.PyQt.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
)

from .styles import STYLE_BTN_PRIMARY


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


# External links (mirrors ui/intro.html).
_URL_CAIO = "https://www.linkedin.com/in/caioarantes/"
_URL_LUCAS = "https://www.linkedin.com/in/lucas-rios-do-amaral-bb302449/"
_URL_FARM = "https://farmanalytica.com.br"
_URL_SITE = "https://www.raviqgis.org"
_URL_MATEUS = "https://www.linkedin.com/in/mateuspinto/"
_URL_AGRIGEE = "https://github.com/mateuspinto/AgriGEE.lite"
_LINK_STYLE = "color:#1b6b39; font-weight:bold; text-decoration:none;"

# Feature overview shown on the Welcome page. Each entry is (name, one-line what).
# Keep names aligned with the per-page intros (optical.py, sysi.py, radar.py).
_FEATURES = [
    ("Optical time series",
     "Per-date Sentinel-2 vegetation-index series (NDVI, EVI, NDRE, NDWI, NBR…) "
     "over your AOI, with SCL cloud/shadow masking and date filtering"),
    ("Custom indices",
     "Build your own index from band math and reuse it across the whole series"),
    ("Synthetic composite",
     "Reduce a series to one image (mean, median, max, AUC…) for a clean snapshot"),
    ("Multispectral RGB",
     "True- and false-colour composites for any acquisition date, styled in QGIS"),
    ("Landsat super-resolution",
     "Pan-sharpened 15 m Landsat 7/8/9 imagery, with a multi-mission vegetation-index "
     "time series — powered by AgriGEE.lite"),
    ("SYSI — synthetic soil image",
     "Bare-soil reflectance composite (GEOS3) from cloud-free pixels for soil mapping"),
    ("Radar (SAR)",
     "Sentinel-1 VV/VH backscatter time series — cloud-independent monitoring"),
    ("DEM download",
     "Fetch terrain elevation models (SRTM, Copernicus…) clipped to your area"),
    ("Climate overlay",
     "Overlay daily NASA POWER precipitation and min/max temperature on the plot"),
    ("Point &amp; feature analysis",
     "Per-feature or per-point series with adjustable buffer and value extraction"),
    ("Batch download &amp; CSV",
     "Export every selected date as rasters and the full data table as CSV"),
]


def _build_intro_section():
    """Full-width banner: condensed RAVI story + an overview of every feature.

    The narrative is distilled from ui/intro.html; the feature grid mirrors the
    per-module intro tabs so the Welcome page doubles as a landing overview.
    """
    frame = QFrame()
    frame.setMinimumWidth(280)
    frame.setStyleSheet("""
        QFrame {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            border-radius: 12px;
        }
        QLabel { background: transparent; border: none; }
    """)
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(18, 14, 18, 14)
    lay.setSpacing(10)

    title = QLabel(_tr("Welcome to FARM tools"))
    title.setStyleSheet("color: #1a1a1a; font-size: 18px; font-weight: bold;")
    lay.addWidget(title)

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

    feat_caption = QLabel(_tr("WHAT YOU CAN DO"))
    feat_caption.setStyleSheet(
        "color: #1b6b39; font-size: 11px; letter-spacing: 1px; font-weight: bold;"
    )
    lay.addWidget(feat_caption)

    # Split the features into two balanced columns of rich-text bullets.
    half = (len(_FEATURES) + 1) // 2
    columns = QHBoxLayout()
    columns.setContentsMargins(0, 0, 0, 0)
    columns.setSpacing(20)
    for chunk in (_FEATURES[:half], _FEATURES[half:]):
        items = "".join(
            f"<p style='margin:0 0 8px 0;'>"
            f"<b style='color:#1b6b39;'>{_tr(name)}</b><br>"
            f"<span style='color:#616161;'>{_tr(desc)}</span></p>"
            for name, desc in chunk
        )
        col = QLabel(items)
        col.setWordWrap(True)
        col.setTextFormat(Qt.TextFormat.RichText)
        col.setAlignment(Qt.AlignmentFlag.AlignTop)
        col.setStyleSheet("font-size: 12px;")
        columns.addWidget(col, 1)
    lay.addLayout(columns)

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
            "<a href='{site}' style='{ls}'>www.raviqgis.org</a> · "
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


def setup_welcome_page(dialog, page):
    """Populate the landing page: scrollable intro banner + a Get-started CTA.

    ``dialog.btn_welcome_continue`` advances to the Auth page (wired here so
    ``farm_tools.py`` need not know about this module).
    """
    page.setStyleSheet("background-color: #f5f5f5;")

    page_lay = QVBoxLayout(page)
    page_lay.setContentsMargins(16, 16, 16, 16)
    page_lay.setSpacing(12)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    scroll.setMinimumHeight(0)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
    scroll.setWidget(_build_intro_section())
    page_lay.addWidget(scroll, 1)

    cta_row = QHBoxLayout()
    cta_row.setContentsMargins(0, 0, 0, 0)
    cta_row.addStretch(1)

    dialog.btn_welcome_continue = QPushButton(_tr("Get started   →"))
    dialog.btn_welcome_continue.setFixedHeight(36)
    dialog.btn_welcome_continue.setCursor(Qt.CursorShape.PointingHandCursor)
    dialog.btn_welcome_continue.setStyleSheet(STYLE_BTN_PRIMARY)
    dialog.btn_welcome_continue.clicked.connect(dialog.show_auth_page)
    cta_row.addWidget(dialog.btn_welcome_continue)

    page_lay.addLayout(cta_row)
