# -*- coding: utf-8 -*-
"""
Radar (SAR) data page for the FARM tools dialog.

Two-tab layout: Inputs (parameters) → Results (output).
Signal connections will be wired externally by ``farm_tools.py`` once the
service layer is in place.
"""

from qgis.core import QgsMapLayerProxyModel, QgsSettings
from qgis.gui import QgsMapLayerComboBox
from qgis.PyQt.QtCore import (
    Qt,
    QCoreApplication,
    QDate,
    QPoint,
    QRect,
    QSize,
)
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .styles import STYLE_BTN_PRIMARY, STYLE_BTN_SECONDARY, STYLE_CHECKBOX
from .webcompat import QWebView


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


_TAB_ACTIVE = """
QPushButton {
    background-color: transparent;
    color: #1b6b39;
    border: none;
    border-bottom: 2px solid #1b6b39;
    font-size: 13px;
    font-weight: bold;
    padding: 0 4px 2px 4px;
    border-radius: 0;
}
"""

_TAB_INACTIVE = """
QPushButton {
    background-color: transparent;
    color: #9e9e9e;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 13px;
    font-weight: normal;
    padding: 0 4px 2px 4px;
    border-radius: 0;
}
QPushButton:hover {
    color: #616161;
    border-bottom-color: #d0d0d0;
}
"""


_POPUP_VIEW_STYLE = (
    "background-color: #ffffff; color: #212121;"
    " selection-background-color: #e8f5e9; selection-color: #1a1a1a;"
)

_SLIDER_STYLE = """
QSlider::groove:horizontal { height: 4px; background: #d6d6d6; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #d6d6d6; border-radius: 2px; }
QSlider::add-page:horizontal { background: #d6d6d6; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #1b6b39; width: 14px; height: 14px;
    margin: -6px 0; border-radius: 7px;
}
QSlider::handle:horizontal:hover { background: #15532d; }
"""

_CALENDAR_STYLE = """
QCalendarWidget QWidget {
    background-color: #ffffff;
    color: #212121;
    alternate-background-color: #f5f5f5;
}
QCalendarWidget QAbstractItemView:enabled {
    background-color: #ffffff;
    color: #212121;
    selection-background-color: #1b6b39;
    selection-color: #ffffff;
}
QCalendarWidget QAbstractItemView:disabled {
    color: #bdbdbd;
}
QCalendarWidget QWidget#qt_calendar_navigationbar {
    background-color: #f8f9fa;
    border-bottom: 1px solid #e0e0e0;
    padding: 2px;
}
QCalendarWidget QToolButton {
    background-color: transparent;
    color: #212121;
    border: none;
    padding: 2px 6px;
    font-size: 12px;
    font-weight: bold;
}
QCalendarWidget QToolButton:hover {
    background-color: #e8f5e9;
    border-radius: 4px;
}
QCalendarWidget QSpinBox {
    background-color: #ffffff;
    color: #212121;
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    padding: 2px 4px;
    font-size: 11px;
}
QCalendarWidget QMenu {
    background-color: #ffffff;
    color: #212121;
    border: 1px solid #e0e0e0;
}
"""


def _field_label(text):
    lbl = QLabel(text)
    lbl.setStyleSheet(
        "color: #8f9691; font-size: 10px; font-weight: bold; letter-spacing: 1px;"
        " background: transparent; border: none;"
    )
    return lbl


def _prepare_field(widget, height=30):
    widget.setFixedHeight(height)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return widget


class FlowLayout(QLayout):
    """Left-to-right layout that wraps items onto new lines when the available
    width runs out. Widening the window packs more controls per line, so fewer
    lines are needed and more options stay visible without scrolling."""

    def __init__(self, parent=None, margin=0, spacing=8):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items = []

    def __del__(self):
        while self.count():
            self.takeAt(0)

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
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(
            margins.left() + margins.right(), margins.top() + margins.bottom()
        )
        return size

    def _do_layout(self, rect, test_only):
        margins = self.contentsMargins()
        effective = rect.adjusted(
            margins.left(), margins.top(), -margins.right(), -margins.bottom()
        )
        x = effective.x()
        y = effective.y()
        line_height = 0
        spacing = self.spacing()
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + spacing
            if next_x - spacing > effective.right() and line_height > 0:
                x = effective.x()
                y = y + line_height + spacing
                next_x = x + hint.width() + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()


def _flow(widgets, spacing=8):
    """Wrap ``widgets`` in a container driven by a FlowLayout."""
    container = QWidget()
    container.setStyleSheet("background: transparent;")
    flow = FlowLayout(container, margin=0, spacing=spacing)
    for w in widgets:
        flow.addWidget(w)
    policy = container.sizePolicy()
    policy.setHeightForWidth(True)
    container.setSizePolicy(policy)
    return container


def _group(widgets, spacing=6):
    """Bundle task-related controls into one tight cluster that the flow treats
    as a single item — they stay shoulder-to-shoulder and never wrap apart,
    while the wider gap between clusters signals they're different tasks."""
    box = QWidget()
    box.setStyleSheet("background: transparent;")
    row = QHBoxLayout(box)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(spacing)
    for w in widgets:
        row.addWidget(w)
    return box


def _labeled(text, widget, lbl_width=None):
    """Group a caption label with its control as a single flow item, so they
    never wrap apart from each other."""
    group = QWidget()
    group.setStyleSheet("background: transparent;")
    row = QHBoxLayout(group)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    lbl = QLabel(text)
    lbl.setStyleSheet(
        "color: #616161; font-size: 12px; background: transparent; border: none;"
    )
    if lbl_width:
        lbl.setMinimumWidth(lbl_width)
    row.addWidget(lbl)
    row.addWidget(widget)
    return group


def _caption(text):
    """Small uppercase group caption — a cheap, scannable visual anchor that
    keeps related controls readable as one cluster after the row wraps."""
    lbl = QLabel(text)
    lbl.setStyleSheet(
        "color: #9e9e9e; font-size: 11px; font-weight: bold; letter-spacing: 1px;"
        " background: transparent; border: none;"
    )
    return lbl


def _make_divider():
    divider = QFrame()
    divider.setFrameShape(QFrame.Shape.HLine)
    divider.setStyleSheet("color: #edf0ee; background: transparent;")
    return divider


def _section_panel():
    panel = QFrame()
    panel.setObjectName("sarSectionPanel")
    panel.setStyleSheet("""
        QFrame#sarSectionPanel {
            background-color: #fbfcfb;
            border: 1px solid #e4ebe6;
            border-radius: 8px;
        }
    """)
    return panel


_INTRO_I18N = {
    "pt": {
        "title": "🛰️ Módulo SAR - FARM tools",
        "desc": 'O módulo SAR do FARM tools fornece uma interface gráfica para processar dados Sentinel-1 usando o <a href="https://www.mdpi.com/2072-4292/13/10/1954">Sentinel-1 SAR Backscatter Analysis Ready Data</a> no Google Earth Engine, sem necessidade de programação.',
        "workflow_h": "📋 Fluxo de Trabalho",
        "wf": ["<b>Inputs:</b> Selecione a área (AOI), datas e parâmetros de processamento", "<b>Run:</b> Execute o processamento para gerar a série temporal", "<b>Results:</b> Visualize gráficos, filtre datas e exporte os resultados"],
        "features_h": "✨ Principais Funcionalidades",
        "features": ["<b>Seleção de Área e Datas:</b> Interface intuitiva para definir AOI e período de análise", "<b>Parâmetros de Processamento:</b> Correção de ruído de borda, nivelamento de terreno, filtragem de speckle", "<b>Múltiplos Índices Espectrais:</b> Escolha entre VV/VH Ratio, RVI ou DpRVI", "<b>Modos de Renderização Flexíveis:</b> RGB com contraste aprimorado ou pseudocolor Viridis", "<b>Série Temporal Interativa:</b> Gráfico Plotly com zoom, pan e hover", "<b>Filtro de Datas:</b> Selecione datas específicas para refinar análise", "<b>Visualização de Imagens:</b> Pré-visualize ou baixe imagens SAR de cada data", "<b>Download em Lote:</b> Baixe múltiplas imagens com progresso e cancelamento", "<b>Exportação CSV:</b> Exporte dados da série temporal com filtro de datas", "<b>Carregamento Automático:</b> Imagens baixadas são carregadas no QGIS automaticamente"],
        "ts_h": "📊 Série Temporal",
        "ts_p": "O plugin gera gráficos interativos mostrando a série temporal da razão VV/VH para sua área de interesse. Use o filtro de datas para focar em períodos específicos e exportar os dados para análise externa.",
        "bands_h": "🖼️ Bandas e Índices Espectrais",
        "bands_p": "Cada imagem SAR contém 3 bandas: as duas polarizações (VV, VH) mais um índice espectral selecionável.",
        "bands": ["<b>Band 1 - VV:</b> Polarização vertical-vertical", "<b>Band 2 - VH:</b> Polarização vertical-horizontal", "<b>Band 3 - Índice Espectral:</b> VV/VH Ratio, RVI ou DpRVI"],
        "bands_note": 'Selecione o índice desejado na aba "Inputs" antes de executar o processamento.',
        "setup_h": "🔧 Configuração Inicial",
        "setup_p": 'Para usar este módulo, você precisa de autenticação no Google Earth Engine através de um <b>Google Cloud Project ID</b>. Configure isso na guia "Auth" do plugin.',
        "cite_h": "📖 Citação",
        "cite_intro": "Qualquer trabalho publicado que utilize este plugin deve citar:",
    },
    "en": {
        "title": "🛰️ SAR Module - FARM tools",
        "desc": 'The FARM tools SAR module provides a graphical interface to process Sentinel-1 data using the <a href="https://www.mdpi.com/2072-4292/13/10/1954">Sentinel-1 SAR Backscatter Analysis Ready Data</a> in Google Earth Engine, without requiring any coding.',
        "workflow_h": "📋 Workflow",
        "wf": ["<b>Inputs:</b> Select area (AOI), dates, and processing parameters", "<b>Run:</b> Execute processing to generate time series", "<b>Results:</b> View charts, filter dates, and export results"],
        "features_h": "✨ Main Features",
        "features": ["<b>Area &amp; Date Selection:</b> Intuitive interface for defining AOI and analysis period", "<b>Processing Parameters:</b> Border noise correction, terrain flattening, speckle filtering", "<b>Multiple Spectral Indices:</b> Choose between VV/VH Ratio, RVI, or DpRVI", "<b>Flexible Render Modes:</b> RGB composites with enhanced contrast or Viridis pseudocolor", "<b>Interactive Time Series:</b> Plotly chart with zoom, pan, and hover", "<b>Date Filter:</b> Select specific dates to refine analysis", "<b>Image Preview:</b> Preview or download SAR images for each date", "<b>Batch Download:</b> Download multiple images with progress and cancel option", "<b>CSV Export:</b> Export time series data with date filtering", "<b>Auto-Load Images:</b> Downloaded images automatically load in QGIS"],
        "ts_h": "📊 Time Series",
        "ts_p": "The plugin generates interactive charts showing the VV/VH Ratio time series for your area of interest. Use the date filter to focus on specific periods and export data for external analysis.",
        "bands_h": "🖼️ Bands &amp; Spectral Indices",
        "bands_p": "Each SAR image contains 3 bands: the two polarizations (VV, VH) plus a selectable spectral index.",
        "bands": ["<b>Band 1 - VV:</b> Vertical-vertical polarization", "<b>Band 2 - VH:</b> Vertical-horizontal polarization", "<b>Band 3 - Spectral Index:</b> VV/VH Ratio, RVI, or DpRVI"],
        "bands_note": 'Select the desired index in the "Inputs" tab before running the processing.',
        "setup_h": "🔧 Initial Setup",
        "setup_p": 'To use this module, you need authentication to Google Earth Engine via a <b>Google Cloud Project ID</b>. Configure this in the "Auth" tab of the plugin.',
        "cite_h": "📖 Citation",
        "cite_intro": "Any published work using this plugin must cite:",
    },
    "fr": {
        "title": "🛰️ Module SAR - FARM tools",
        "desc": "Le module SAR d'FARM tools fournit une interface graphique pour traiter les données Sentinel-1 dans Google Earth Engine, sans aucune programmation.",
        "workflow_h": "📋 Flux de Travail",
        "wf": ["<b>Inputs :</b> Sélectionnez la zone (AOI), les dates et les paramètres", "<b>Run :</b> Lancez le traitement pour générer la série chronologique", "<b>Results :</b> Affichez les graphiques, filtrez les dates et exportez les résultats"],
        "features_h": "✨ Principales Fonctionnalités",
        "features": ["<b>Sélection de Zone et Dates :</b> Interface intuitive pour définir l'AOI", "<b>Paramètres de Traitement :</b> Correction du bruit de bordure, terrain, speckle", "<b>Indices Spectraux Multiples :</b> Ratio VV/VH, RVI ou DpRVI", "<b>Modes de Rendu Flexibles :</b> RGB ou pseudocolor Viridis", "<b>Séries Temporelles Interactives :</b> Graphique Plotly avec zoom et survol", "<b>Filtre de Dates :</b> Sélectionnez des dates spécifiques", "<b>Aperçu d'Images :</b> Prévisualisez ou téléchargez les images SAR", "<b>Téléchargement par Lots :</b> Téléchargez plusieurs images avec progression", "<b>Exportation CSV :</b> Exportez les données avec filtrage par date", "<b>Chargement Automatique :</b> Les images se chargent automatiquement dans QGIS"],
        "ts_h": "📊 Séries Temporelles",
        "ts_p": "Le plugin génère des graphiques interactifs montrant la série chronologique du Ratio VV/VH pour votre zone d'intérêt.",
        "bands_h": "🖼️ Bandes et Indices Spectraux",
        "bands_p": "Chaque image SAR contient 3 bandes : les deux polarisations (VV, VH) plus un indice spectral sélectionnable.",
        "bands": ["<b>Band 1 - VV :</b> Polarisation verticale-verticale", "<b>Band 2 - VH :</b> Polarisation verticale-horizontale", "<b>Band 3 - Indice Spectral :</b> Ratio VV/VH, RVI ou DpRVI"],
        "bands_note": 'Sélectionnez l\'indice souhaité dans l\'onglet "Inputs" avant de lancer le traitement.',
        "setup_h": "🔧 Configuration Initiale",
        "setup_p": "Pour utiliser ce module, vous avez besoin d'une authentification Google Earth Engine via un <b>Google Cloud Project ID</b>.",
        "cite_h": "📖 Citation",
        "cite_intro": "Tout travail publié utilisant ce plugin doit citer :",
    },
    "es": {
        "title": "🛰️ Módulo SAR - FARM tools",
        "desc": "El módulo SAR de FARM tools proporciona una interfaz gráfica para procesar datos Sentinel-1 en Google Earth Engine, sin necesidad de programación.",
        "workflow_h": "📋 Flujo de Trabajo",
        "wf": ["<b>Inputs:</b> Selecciona el área (AOI), fechas y parámetros", "<b>Run:</b> Ejecuta el procesamiento para generar la serie temporal", "<b>Results:</b> Visualiza gráficos, filtra fechas y exporta los resultados"],
        "features_h": "✨ Funcionalidades Principales",
        "features": ["<b>Selección de Área y Fechas:</b> Interfaz intuitiva para definir AOI", "<b>Parámetros de Procesamiento:</b> Corrección de ruido de borde, terreno, speckle", "<b>Múltiples Índices Espectrales:</b> Razón VV/VH, RVI o DpRVI", "<b>Modos de Renderización:</b> RGB o pseudocolor Viridis", "<b>Serie Temporal Interactiva:</b> Gráfico Plotly con zoom y hover", "<b>Filtro de Fechas:</b> Selecciona fechas específicas", "<b>Vista Previa:</b> Previsualiza o descarga imágenes SAR", "<b>Descarga por Lotes:</b> Descarga múltiples imágenes con progreso", "<b>Exportación CSV:</b> Exporta datos con filtro de fechas", "<b>Carga Automática:</b> Las imágenes se cargan automáticamente en QGIS"],
        "ts_h": "📊 Serie Temporal",
        "ts_p": "El plugin genera gráficos interactivos que muestran la serie temporal de la Razón VV/VH para tu área de interés.",
        "bands_h": "🖼️ Bandas e Índices Espectrales",
        "bands_p": "Cada imagen SAR contiene 3 bandas: las dos polarizaciones (VV, VH) más un índice espectral seleccionable.",
        "bands": ["<b>Band 1 - VV:</b> Polarización vertical-vertical", "<b>Band 2 - VH:</b> Polarización vertical-horizontal", "<b>Band 3 - Índice Espectral:</b> Razón VV/VH, RVI o DpRVI"],
        "bands_note": 'Selecciona el índice deseado en la pestaña "Inputs" antes de ejecutar.',
        "setup_h": "🔧 Configuración Inicial",
        "setup_p": 'Para usar este módulo necesitas autenticación en Google Earth Engine via <b>Google Cloud Project ID</b>. Configúralo en la pestaña "Auth".',
        "cite_h": "📖 Citación",
        "cite_intro": "Cualquier trabajo publicado que utilice este plugin debe citar:",
    },
    "it": {
        "title": "🛰️ Modulo SAR - FARM tools",
        "desc": "Il modulo SAR di FARM tools fornisce un'interfaccia grafica per elaborare i dati Sentinel-1 in Google Earth Engine, senza necessità di programmazione.",
        "workflow_h": "📋 Flusso di Lavoro",
        "wf": ["<b>Inputs:</b> Seleziona l'area (AOI), le date e i parametri", "<b>Run:</b> Esegui l'elaborazione per generare la serie temporale", "<b>Results:</b> Visualizza i grafici, filtra le date ed esporta i risultati"],
        "features_h": "✨ Funzionalità Principali",
        "features": ["<b>Selezione di Area e Date:</b> Interfaccia intuitiva per definire AOI", "<b>Parametri di Elaborazione:</b> Correzione rumore, terreno, speckle", "<b>Indici Spettrali Multipli:</b> Rapporto VV/VH, RVI o DpRVI", "<b>Modalità di Rendering:</b> RGB o pseudocolor Viridis", "<b>Serie Temporali Interattive:</b> Grafico Plotly con zoom e hover", "<b>Filtro Date:</b> Seleziona date specifiche", "<b>Anteprima Immagini:</b> Anteprima o download delle immagini SAR", "<b>Download in Batch:</b> Scarica più immagini con avanzamento", "<b>Esportazione CSV:</b> Esporta dati con filtro per data", "<b>Caricamento Automatico:</b> Le immagini si caricano automaticamente in QGIS"],
        "ts_h": "📊 Serie Temporali",
        "ts_p": "Il plugin genera grafici interattivi che mostrano la serie temporale del Rapporto VV/VH per la tua area di interesse.",
        "bands_h": "🖼️ Bande e Indici Spettrali",
        "bands_p": "Ogni immagine SAR contiene 3 bande: le due polarizzazioni (VV, VH) più un indice spettrale selezionabile.",
        "bands": ["<b>Band 1 - VV:</b> Polarizzazione verticale-verticale", "<b>Band 2 - VH:</b> Polarizzazione verticale-orizzontale", "<b>Band 3 - Indice Spettrale:</b> Rapporto VV/VH, RVI o DpRVI"],
        "bands_note": 'Seleziona l\'indice desiderato nella scheda "Inputs" prima di eseguire.',
        "setup_h": "🔧 Configurazione Iniziale",
        "setup_p": 'Per usare questo modulo hai bisogno dell\'autenticazione a Google Earth Engine tramite <b>Google Cloud Project ID</b>. Configuralo nella scheda "Auth".',
        "cite_h": "📖 Citazione",
        "cite_intro": "Qualsiasi lavoro pubblicato che utilizza questo plugin deve citare:",
    },
}
_INTRO_I18N["zh"] = _INTRO_I18N["en"]
_INTRO_I18N["hi"] = _INTRO_I18N["en"]

_CITE_REF = (
    "Mullissa, A.; Vollrath, A.; Odongo-Braun, C.; Slagter, B.; Balling, J.; Gou, Y.; "
    "Gorelick, N.; Reiche, J. Sentinel-1 SAR Backscatter Analysis Ready Data Preparation "
    "in Google Earth Engine. Remote Sens. 2021, 13, 1954. "
    "https://doi.org/10.3390/rs13101954"
)


def _build_intro_tab(_dialog, parent):
    """Build the Intro tab using native Qt widgets (no WebView)."""
    locale = QgsSettings().value("locale/userLocale", "en_US") or "en_US"
    t = _INTRO_I18N.get(locale[:2].lower(), _INTRO_I18N["en"])

    outer = QVBoxLayout(parent)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setStyleSheet("QScrollArea { background: #ffffff; border: none; }")

    w = QWidget()
    w.setStyleSheet("background: #ffffff;")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(24, 16, 24, 16)
    lay.setSpacing(4)

    def _lbl(html, style=""):
        l = QLabel(html)
        l.setWordWrap(True)
        l.setOpenExternalLinks(True)
        l.setTextFormat(Qt.TextFormat.RichText)
        if style:
            l.setStyleSheet(style)
        return l

    def _h1(text):
        return _lbl(text, "font-size:15px;font-weight:bold;color:#1b6b39;margin-bottom:4px;")

    def _h2(text):
        return _lbl(text, "font-size:12px;font-weight:bold;color:#2a5d84;"
                          "padding-bottom:3px;margin-top:12px;margin-bottom:2px;")

    def _para(html):
        return _lbl(html, "font-size:12px;color:#333;")

    def _divider():
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color:#e6f2fa;")
        return line

    lay.addWidget(_h1(t["title"]))
    lay.addSpacing(2)
    lay.addWidget(_para(t["desc"]))

    lay.addWidget(_h2(t["workflow_h"]))
    lay.addWidget(_divider())
    wf_frame = QFrame()
    wf_frame.setStyleSheet(
        "QFrame{background:#f0f8ff;border-radius:4px;padding:4px;}"
    )
    wf_lay = QVBoxLayout(wf_frame)
    wf_lay.setContentsMargins(12, 6, 12, 6)
    wf_lay.setSpacing(4)
    for i, text in enumerate(t["wf"], 1):
        wf_lay.addWidget(_para(f"{i}. {text}"))
    lay.addWidget(wf_frame)

    lay.addWidget(_h2(t["features_h"]))
    lay.addWidget(_divider())
    for text in t["features"]:
        lay.addWidget(_para(f"✓  {text}"))

    lay.addWidget(_h2(t["ts_h"]))
    lay.addWidget(_divider())
    lay.addWidget(_para(t["ts_p"]))

    lay.addWidget(_h2(t["bands_h"]))
    lay.addWidget(_divider())
    lay.addWidget(_para(t["bands_p"]))
    for text in t["bands"]:
        lay.addWidget(_para(f"• {text}"))
    lay.addWidget(_para(t["bands_note"]))

    lay.addWidget(_h2(t["setup_h"]))
    lay.addWidget(_divider())
    lay.addWidget(_para(t["setup_p"]))

    lay.addWidget(_h2(t["cite_h"]))
    lay.addWidget(_divider())
    lay.addWidget(_para(t["cite_intro"]))
    cite_frame = QFrame()
    cite_frame.setStyleSheet(
        "QFrame{background:#e8f5e9;border-left:4px solid #1b6b39;border-radius:3px;}"
    )
    cite_lay = QVBoxLayout(cite_frame)
    cite_lay.setContentsMargins(12, 8, 12, 8)
    ref = _lbl(
        _CITE_REF,
        "font-family:monospace;font-size:11px;background:#fff;"
        "padding:6px;border:1px solid #c8e6c9;border-radius:3px;",
    )
    cite_lay.addWidget(ref)
    lay.addWidget(cite_frame)

    lay.addStretch(1)
    scroll.setWidget(w)
    outer.addWidget(scroll, 1)


def _build_inputs_tab(dialog, parent):
    outer = QVBoxLayout(parent)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

    scroll_w = QWidget()
    scroll_w.setStyleSheet("background: transparent;")
    lay = QVBoxLayout(scroll_w)
    lay.setContentsMargins(6, 16, 6, 14)
    lay.setSpacing(12)

    inputs_panel = _section_panel()
    inputs_lay = QVBoxLayout(inputs_panel)
    inputs_lay.setContentsMargins(16, 14, 16, 14)
    inputs_lay.setSpacing(10)

    inputs_lay.addWidget(_field_label(_tr("AOI LAYER")))

    aoi_row = QWidget()
    aoi_row_lay = QHBoxLayout(aoi_row)
    aoi_row_lay.setContentsMargins(0, 0, 0, 0)
    aoi_row_lay.setSpacing(6)

    dialog.sar_layer_combo = QgsMapLayerComboBox()
    dialog.sar_layer_combo.setFilters(QgsMapLayerProxyModel.VectorLayer)
    _prepare_field(dialog.sar_layer_combo)
    dialog.sar_layer_combo.setAllowEmptyLayer(True)
    dialog.sar_layer_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)
    aoi_row_lay.addWidget(dialog.sar_layer_combo, 1)

    dialog.sar_btn_draw_aoi = QPushButton(_tr("Draw AOI"))
    dialog.sar_btn_draw_aoi.setToolTip(
        _tr("Drag on the map to draw a box (Shift = square, Esc = cancel)")
    )
    dialog.sar_btn_draw_aoi.setFixedHeight(28)
    dialog.sar_btn_draw_aoi.setSizePolicy(
        QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
    )
    dialog.sar_btn_draw_aoi.adjustSize()
    dialog.sar_btn_draw_aoi.setStyleSheet(STYLE_BTN_SECONDARY)
    aoi_row_lay.addWidget(dialog.sar_btn_draw_aoi)

    dialog.sar_btn_hybrid_layer = QPushButton(_tr("Add Google Hybrid Layer"))
    dialog.sar_btn_hybrid_layer.setFixedHeight(28)
    dialog.sar_btn_hybrid_layer.setSizePolicy(
        QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
    )
    dialog.sar_btn_hybrid_layer.adjustSize()
    dialog.sar_btn_hybrid_layer.setStyleSheet(STYLE_BTN_SECONDARY)
    aoi_row_lay.addWidget(dialog.sar_btn_hybrid_layer)

    inputs_lay.addWidget(aoi_row)

    inputs_lay.addSpacing(6)

    fields_grid = QGridLayout()
    fields_grid.setContentsMargins(0, 0, 0, 0)
    fields_grid.setHorizontalSpacing(16)
    fields_grid.setVerticalSpacing(8)
    fields_grid.setColumnStretch(0, 1)
    fields_grid.setColumnStretch(1, 1)

    dialog.sar_date_start = QDateEdit()
    dialog.sar_date_start.setDisplayFormat("yyyy-MM-dd")
    dialog.sar_date_start.setCalendarPopup(True)
    dialog.sar_date_start.setDate(QDate.currentDate().addYears(-1))
    _prepare_field(dialog.sar_date_start)
    dialog.sar_date_end = QDateEdit()
    dialog.sar_date_end.setDisplayFormat("yyyy-MM-dd")
    dialog.sar_date_end.setCalendarPopup(True)
    dialog.sar_date_end.setDate(QDate.currentDate())
    _prepare_field(dialog.sar_date_end)
    for _cal in (
        dialog.sar_date_start.calendarWidget(),
        dialog.sar_date_end.calendarWidget(),
    ):
        if _cal is not None:
            _cal.setStyleSheet(_CALENDAR_STYLE)

    fields_grid.addWidget(_field_label(_tr("START DATE")), 0, 0)
    fields_grid.addWidget(_field_label(_tr("END DATE")), 0, 1)
    fields_grid.addWidget(dialog.sar_date_start, 1, 0)
    fields_grid.addWidget(dialog.sar_date_end, 1, 1)

    dialog.sar_pol_combo = QComboBox()
    dialog.sar_pol_combo.addItems(["VV", "VH", "VVVH"])
    dialog.sar_pol_combo.setCurrentText("VVVH")
    _prepare_field(dialog.sar_pol_combo)
    dialog.sar_pol_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)
    dialog.sar_format_combo = QComboBox()
    dialog.sar_format_combo.addItems(["DB", "LINEAR"])
    _prepare_field(dialog.sar_format_combo)
    dialog.sar_format_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)
    dialog.sar_index_combo = QComboBox()
    dialog.sar_index_combo.addItems([
        "VV/VH Ratio", "RVI", "DpRVI",
        "Cross Ratio (VH/VV)", "NDPI", "Pol Difference (VV-VH)",
        "DPSVIm", "PRVI", "mRVI",
    ])
    dialog.sar_index_combo.setCurrentText("VV/VH Ratio")
    _prepare_field(dialog.sar_index_combo)
    dialog.sar_index_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)

    fields_grid.addWidget(_field_label(_tr("POLARIZATION")), 2, 0)
    fields_grid.addWidget(_field_label(_tr("OUTPUT FORMAT")), 2, 1)
    fields_grid.addWidget(_field_label(_tr("SPECTRAL INDEX TIME SERIES")), 4, 0)
    fields_grid.addWidget(dialog.sar_pol_combo, 3, 0)
    fields_grid.addWidget(dialog.sar_format_combo, 3, 1)
    fields_grid.addWidget(dialog.sar_index_combo, 5, 0)
    inputs_lay.addLayout(fields_grid)

    index_info = {
        "VV/VH Ratio": _tr(
            "<b>VV/VH Ratio</b> — ratio between co-polarized (VV) and "
            "cross-polarized (VH) backscatter. Cross-pol rises with volume "
            "scattering from vegetation, so the ratio tracks canopy structure "
            "and biomass.<br><i>Formula:</i> VV / VH"
            "<br><i>Use for:</i> crop growth monitoring, "
            "vegetation vs. bare-soil discrimination, flood/water mapping."
        ),
        "RVI": _tr(
            "<b>RVI (Radar Vegetation Index)</b> — normalized dual-pol index "
            "(≈0 over smooth bare soil, →1 over dense randomly-oriented "
            "canopy), robust to incidence angle.<br><i>Formula:</i> "
            "(4 × VH) / (VV + VH)"
            "<br><i>Use for:</i> vegetation "
            "cover and biomass estimation, crop phenology tracking, drought "
            "stress detection."
        ),
        "DpRVI": _tr(
            "<b>DpRVI (Dual-pol Radar Vegetation Index)</b> — derived from the "
            "degree of polarization and eigenvalue decomposition of the "
            "dual-pol covariance matrix; physically-based and more sensitive "
            "across the growth cycle than RVI.<br><i>Formula:</i> "
            "VH / (VV + VH)"
            "<br><i>Use for:</i> crop "
            "biophysical parameter retrieval, soil-moisture vs. vegetation "
            "separation, detailed phenology."
        ),
        "Cross Ratio (VH/VV)": _tr(
            "<b>Cross Ratio (CR)</b> — cross- over co-polarized backscatter. "
            "Rises strongly with green biomass and canopy volume; one of the "
            "most widely used Sentinel-1 crop indicators.<br><i>Formula:</i> "
            "VH / VV"
            "<br><i>Use for:</i> crop growth and biomass, phenology, "
            "vegetation density."
        ),
        "NDPI": _tr(
            "<b>NDPI (Normalized Difference Polarization Index)</b> — normalized "
            "contrast between co- and cross-pol backscatter (also used as RFDI "
            "for forest degradation).<br><i>Formula:</i> (VV − VH) / (VV + VH)"
            "<br><i>Use for:</i> vegetation vs. soil/water separation, forest "
            "disturbance, land-cover discrimination."
        ),
        "Pol Difference (VV-VH)": _tr(
            "<b>Polarization Difference (PD)</b> — absolute gap between co- and "
            "cross-pol backscatter; a simple proxy for scattering "
            "structure.<br><i>Formula:</i> VV − VH"
            "<br><i>Use for:</i> biomass/structure trends, surface vs. volume "
            "scattering, quick change detection."
        ),
        "DPSVIm": _tr(
            "<b>DPSVIm (Modified Dual-pol SAR Vegetation Index)</b> — practical "
            "successor to DPSVI; no per-scene maximum needed, sensitive across "
            "the crop cycle.<br><i>Formula:</i> VV × (VV + VH) / √2"
            "<br><i>Use for:</i> crop biomass and LAI, soil-moisture-robust "
            "vegetation monitoring. Use LINEAR output format."
        ),
        "PRVI": _tr(
            "<b>PRVI (Polarimetric Radar Vegetation Index)</b> — weights cross-"
            "pol backscatter by the degree of depolarization.<br><i>Formula:</i> "
            "(1 − VH / VV) × VH"
            "<br><i>Use for:</i> vegetation cover and biomass, canopy density "
            "estimation."
        ),
        "mRVI": _tr(
            "<b>mRVI (Modified Radar Vegetation Index)</b> — bounded RVI variant "
            "scaled by the co-pol fraction for steadier dynamic "
            "range.<br><i>Formula:</i> √(VV / (VV + VH)) × (4 × VH / (VV + VH))"
            "<br><i>Use for:</i> vegetation cover and biomass, phenology "
            "tracking."
        ),
    }
    dialog.sar_index_info = QLabel()
    dialog.sar_index_info.setWordWrap(True)
    dialog.sar_index_info.setTextFormat(Qt.TextFormat.RichText)
    dialog.sar_index_info.setStyleSheet(
        "color: #4a5650; font-size: 11px; background: #f0f8ff;"
        " border: 1px solid #d6e4ef; border-radius: 6px; padding: 8px;"
    )

    def _update_index_info(name):
        dialog.sar_index_info.setText(index_info.get(name, ""))

    dialog.sar_index_combo.currentTextChanged.connect(_update_index_info)
    _update_index_info(dialog.sar_index_combo.currentText())
    inputs_lay.addWidget(dialog.sar_index_info)

    lay.addWidget(inputs_panel)

    options_panel = _section_panel()
    options_lay = QVBoxLayout(options_panel)
    options_lay.setContentsMargins(16, 12, 16, 14)
    options_lay.setSpacing(10)
    options_lay.addWidget(_field_label(_tr("PROCESSING OPTIONS")))

    options_row = QHBoxLayout()
    options_row.setContentsMargins(0, 0, 0, 0)
    options_row.setSpacing(24)

    dialog.sar_chk_border_noise = QCheckBox(_tr("Border noise correction"))
    dialog.sar_chk_border_noise.setChecked(True)
    dialog.sar_chk_terrain = QCheckBox(_tr("Terrain flattening"))
    dialog.sar_chk_terrain.setChecked(True)
    dialog.sar_chk_speckle = QCheckBox(_tr("Speckle filtering"))
    dialog.sar_chk_speckle.setChecked(True)
    for chk in (
        dialog.sar_chk_border_noise,
        dialog.sar_chk_terrain,
        dialog.sar_chk_speckle,
    ):
        chk.setStyleSheet(STYLE_CHECKBOX)
        options_row.addWidget(chk)
    options_row.addStretch(1)
    options_lay.addLayout(options_row)
    lay.addWidget(options_panel)

    lay.addStretch(1)
    scroll.setWidget(scroll_w)
    outer.addWidget(scroll)


def _build_results_tab(dialog, parent):
    outer = QVBoxLayout(parent)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    dialog.sar_results_splitter = QSplitter(Qt.Orientation.Vertical)
    dialog.sar_results_splitter.setChildrenCollapsible(False)
    dialog.sar_results_splitter.setHandleWidth(4)
    dialog.sar_results_splitter.setStyleSheet("""
        QSplitter::handle {
            background: transparent;
            margin: 0px 6px;
            border-top: 2px solid #d6e0d9;
        }
        QSplitter::handle:hover { border-top-color: #1b6b39; }
    """)

    dialog.sar_web_view = QWebView()
    dialog.sar_web_view.setStyleSheet(
        "border: 1px solid #dce6df; border-radius: 8px; background: #ffffff;"
    )
    dialog.sar_web_view.setMinimumHeight(200)
    dialog.sar_results_splitter.addWidget(dialog.sar_web_view)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

    scroll_w = QWidget()
    scroll_w.setStyleSheet("background: transparent;")
    lay = QVBoxLayout(scroll_w)
    lay.setContentsMargins(6, 0, 6, 14)
    lay.setSpacing(12)

    controls_panel = _section_panel()
    controls_lay = QVBoxLayout(controls_panel)
    controls_lay.setContentsMargins(16, 14, 16, 14)
    controls_lay.setSpacing(10)

    controls_lay.addWidget(_caption(_tr("TIME SERIES")))
    dialog.sar_btn_filter_dates = QPushButton(_tr("Filter dates"))
    dialog.sar_btn_filter_dates.setFixedHeight(30)
    dialog.sar_btn_filter_dates.setStyleSheet(STYLE_BTN_SECONDARY)
    dialog.sar_btn_open_browser = QPushButton(_tr("Open in Browser"))
    dialog.sar_btn_open_browser.setFixedHeight(30)
    dialog.sar_btn_open_browser.setStyleSheet(STYLE_BTN_SECONDARY)
    dialog.sar_btn_download_csv = QPushButton(_tr("Export CSV"))
    dialog.sar_btn_download_csv.setFixedHeight(30)
    dialog.sar_btn_download_csv.setStyleSheet(STYLE_BTN_SECONDARY)
    dialog.sar_btn_batch_download = QPushButton(_tr("Batch Download (All Dates)"))
    dialog.sar_btn_batch_download.setFixedHeight(30)
    dialog.sar_btn_batch_download.setStyleSheet(STYLE_BTN_SECONDARY)
    controls_lay.addWidget(_flow([
        dialog.sar_btn_filter_dates,
        dialog.sar_btn_open_browser,
        dialog.sar_btn_download_csv,
        dialog.sar_btn_batch_download,
    ]))

    controls_lay.addWidget(_make_divider())

    controls_lay.addWidget(_caption(_tr("SINGLE-DATE IMAGE")))
    dialog.sar_result_date_combo = QComboBox()
    _prepare_field(dialog.sar_result_date_combo, 30)
    dialog.sar_result_date_combo.setMinimumWidth(136)
    dialog.sar_result_date_combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToContents
    )
    dialog.sar_result_date_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)

    dialog.sar_render_combo = QComboBox()
    _prepare_field(dialog.sar_render_combo, 30)
    dialog.sar_render_combo.setMinimumWidth(240)
    dialog.sar_render_combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToContents
    )
    # Canonical English key in itemData drives the renderer, so the selection
    # keeps working under translated UI labels.
    for _label, _key in (
        (_tr("RGB: VV, VH, VV/VH Ratio"), "RGB: VV, VH, VV/VH Ratio"),
        (_tr("RGB: VV, VH, CR"), "RGB: VV, VH, CR"),
        (_tr("RGB: VV, VH, RVI"), "RGB: VV, VH, RVI"),
        (_tr("RGB: VV, VH, NDPI"), "RGB: VV, VH, NDPI"),
        (_tr("RGB: VV, VH, PD"), "RGB: VV, VH, PD"),
        (_tr("RGB: VV, RVI, DpRVI"), "RGB: VV, RVI, DpRVI"),
        (_tr("RGB: VV, VV/VH Ratio, RVI"), "RGB: VV, VV/VH Ratio, RVI"),
        (_tr("RGB: VV/VH Ratio, RVI, DpRVI"), "RGB: VV/VH Ratio, RVI, DpRVI"),
        (_tr("RGB: CR, RVI, DpRVI"), "RGB: CR, RVI, DpRVI"),
        (_tr("RGB: RVI, DpRVI, mRVI"), "RGB: RVI, DpRVI, mRVI"),
        (_tr("RGB: NDPI, RVI, DPSVIm"), "RGB: NDPI, RVI, DPSVIm"),
        (_tr("Band: VV"), "Band: VV"),
        (_tr("Band: VH"), "Band: VH"),
        (_tr("Band: VV/VH Ratio"), "Band: VV/VH Ratio"),
        (_tr("Band: RVI"), "Band: RVI"),
        (_tr("Band: DpRVI"), "Band: DpRVI"),
        (_tr("Band: CR"), "Band: CR"),
        (_tr("Band: NDPI"), "Band: NDPI"),
        (_tr("Band: PD"), "Band: PD"),
        (_tr("Band: DPSVIm"), "Band: DPSVIm"),
        (_tr("Band: PRVI"), "Band: PRVI"),
        (_tr("Band: mRVI"), "Band: mRVI"),
    ):
        dialog.sar_render_combo.addItem(_label, _key)
    dialog.sar_render_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)

    dialog.sar_render_ramp_combo = QComboBox()
    _prepare_field(dialog.sar_render_ramp_combo, 30)
    dialog.sar_render_ramp_combo.setMinimumWidth(140)
    dialog.sar_render_ramp_combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToContents
    )
    dialog.sar_render_ramp_combo.addItems([
        "Viridis", "Magma", "Plasma", "Inferno", "RdYlGn", "Greys",
    ])
    # Explicit disabled look — the page stylesheet keeps QComboBox white, so the
    # plain enabled/disabled state is not visible without this override.
    dialog.sar_render_ramp_combo.setStyleSheet(
        "QComboBox:disabled { color: #bdbdbd; background: #f2f2f2;"
        " border-color: #e6e6e6; }"
    )
    dialog.sar_render_ramp_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)

    dialog.sar_btn_preview = QPushButton(_tr("Preview"))
    dialog.sar_btn_preview.setFixedHeight(30)
    dialog.sar_btn_preview.setStyleSheet(STYLE_BTN_PRIMARY)
    dialog.sar_btn_download_preview = QPushButton(
        _tr("Download & Preview").replace("&", "&&")
    )
    dialog.sar_btn_download_preview.setFixedHeight(30)
    dialog.sar_btn_download_preview.setStyleSheet(STYLE_BTN_SECONDARY)

    # The color ramp only applies to single-band ("Band: …") renders. Build the
    # caption manually (not via _labeled) so it can be dimmed in lockstep with
    # the disabled combo for the RGB composites where the ramp has no effect.
    ramp_label = QLabel(_tr("Color Ramp"))
    ramp_label.setMinimumWidth(80)
    _RAMP_LBL_ON = (
        "color: #616161; font-size: 12px; background: transparent; border: none;"
    )
    _RAMP_LBL_OFF = (
        "color: #bdbdbd; font-size: 12px; background: transparent; border: none;"
    )
    ramp_group = QWidget()
    ramp_group.setStyleSheet("background: transparent;")
    ramp_row = QHBoxLayout(ramp_group)
    ramp_row.setContentsMargins(0, 0, 0, 0)
    ramp_row.setSpacing(8)
    ramp_row.addWidget(ramp_label)
    ramp_row.addWidget(dialog.sar_render_ramp_combo)

    def _sync_render_ramp():
        is_band = str(dialog.sar_render_combo.currentData()).startswith("Band: ")
        dialog.sar_render_ramp_combo.setEnabled(is_band)
        ramp_label.setStyleSheet(_RAMP_LBL_ON if is_band else _RAMP_LBL_OFF)

    dialog.sar_render_combo.currentIndexChanged.connect(
        lambda _i: _sync_render_ramp()
    )
    _sync_render_ramp()

    # Each control is its own flow item (date+filter kept as one tight cluster)
    # so the row wraps onto new lines when the panel is narrow — the section
    # grows taller instead of clipping the buttons.
    controls_lay.addWidget(_flow([
        _labeled(_tr("Date"), dialog.sar_result_date_combo, 34),
        _labeled(_tr("Render Mode"), dialog.sar_render_combo, 80),
        ramp_group,
        dialog.sar_btn_preview,
        dialog.sar_btn_download_preview,
    ], spacing=12))
    lay.addWidget(controls_panel)

    composite_panel = _section_panel()
    composite_lay = QVBoxLayout(composite_panel)
    composite_lay.setContentsMargins(16, 14, 16, 14)
    composite_lay.setSpacing(10)

    composite_title = QLabel(_tr("SYNTHETIC IMAGE (COMPOSITE)"))
    composite_title.setStyleSheet(
        "color: #9e9e9e; font-size: 11px; font-weight: bold; letter-spacing: 1px;"
        " background: transparent; border: none;"
    )
    composite_lay.addWidget(composite_title)

    composite_hint = QLabel(
        _tr("Composite the selected index over the selected dates.")
    )
    composite_hint.setWordWrap(True)
    composite_hint.setStyleSheet(
        "color: #616161; font-size: 11px; background: transparent; border: none;"
    )
    composite_lay.addWidget(composite_hint)

    dialog.sar_composite_metric_combo = QComboBox()
    _prepare_field(dialog.sar_composite_metric_combo, 30)
    dialog.sar_composite_metric_combo.setMinimumWidth(240)
    dialog.sar_composite_metric_combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToContents
    )
    for _metric_key in (
        "Mean",
        "Median",
        "Min",
        "Max",
        "Amplitude",
        "Standard Deviation",
        "Sum",
        "Area Under Curve (AUC)",
    ):
        dialog.sar_composite_metric_combo.addItem(_tr(_metric_key), _metric_key)
    dialog.sar_composite_metric_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)

    dialog.sar_composite_ramp_combo = QComboBox()
    _prepare_field(dialog.sar_composite_ramp_combo, 30)
    dialog.sar_composite_ramp_combo.setMinimumWidth(240)
    dialog.sar_composite_ramp_combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToContents
    )
    dialog.sar_composite_ramp_combo.addItems([
        "Viridis",
        "Magma",
        "Plasma",
        "Inferno",
        "RdYlGn",
        "Greys",
    ])
    dialog.sar_composite_ramp_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)

    dialog.sar_btn_composite_preview = QPushButton(_tr("Preview Composite"))
    dialog.sar_btn_composite_preview.setFixedHeight(30)
    dialog.sar_btn_composite_preview.setStyleSheet(STYLE_BTN_PRIMARY)
    dialog.sar_btn_composite_download = QPushButton(
        _tr("Download & Preview").replace("&", "&&")
    )
    dialog.sar_btn_composite_download.setFixedHeight(30)
    dialog.sar_btn_composite_download.setStyleSheet(STYLE_BTN_SECONDARY)

    # Flat flow so each control wraps onto a new line when the panel is narrow,
    # growing the section vertically instead of clipping the buttons.
    composite_lay.addWidget(_flow([
        _labeled(_tr("Metric"), dialog.sar_composite_metric_combo, 80),
        _labeled(_tr("Color Ramp"), dialog.sar_composite_ramp_combo, 80),
        dialog.sar_btn_composite_preview,
        dialog.sar_btn_composite_download,
    ], spacing=12))

    lay.addWidget(composite_panel)

    buffer_panel = _section_panel()
    buffer_lay = QVBoxLayout(buffer_panel)
    buffer_lay.setContentsMargins(16, 14, 16, 14)
    buffer_lay.setSpacing(10)

    buffer_lay.addWidget(_caption(_tr("DOWNLOAD BUFFER")))
    buffer_hint = QLabel(
        _tr("Use a positive buffer to include terrain just outside your area, "
            "or a negative buffer to crop the edges. Applies to every "
            "downloaded and previewed SAR output (single date, batch, composite).")
    )
    buffer_hint.setWordWrap(True)
    buffer_hint.setStyleSheet(
        "color: #757575; font-size: 11px; background: transparent; border: none;"
    )
    buffer_lay.addWidget(buffer_hint)

    buffer_row = QHBoxLayout()
    buffer_row.setContentsMargins(0, 0, 0, 0)
    buffer_row.setSpacing(8)

    minus_lbl = QLabel("−300 m")
    minus_lbl.setStyleSheet(
        "color: #9e9e9e; font-size: 9px; background: transparent; border: none;"
    )
    buffer_row.addWidget(minus_lbl)

    dialog.sar_buffer_slider = QSlider(Qt.Orientation.Horizontal)
    dialog.sar_buffer_slider.setMinimum(-300)
    dialog.sar_buffer_slider.setMaximum(300)
    dialog.sar_buffer_slider.setSingleStep(1)
    dialog.sar_buffer_slider.setPageStep(10)
    dialog.sar_buffer_slider.setValue(0)
    dialog.sar_buffer_slider.setTickInterval(100)
    dialog.sar_buffer_slider.setTickPosition(QSlider.TickPosition.NoTicks)
    dialog.sar_buffer_slider.setStyleSheet(_SLIDER_STYLE)
    buffer_row.addWidget(dialog.sar_buffer_slider, 1)

    plus_lbl = QLabel("+300 m")
    plus_lbl.setStyleSheet(
        "color: #9e9e9e; font-size: 9px; background: transparent; border: none;"
    )
    buffer_row.addWidget(plus_lbl)

    buffer_lay.addLayout(buffer_row)

    dialog.sar_buffer_value = QLabel(_tr("Buffer: 0 m"))
    dialog.sar_buffer_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
    dialog.sar_buffer_value.setStyleSheet(
        "color: #616161; font-size: 10px; background: transparent; border: none;"
    )
    buffer_lay.addWidget(dialog.sar_buffer_value)

    def _set_sar_buffer_value(value):
        value = 0 if -3 <= value <= 3 else value
        if dialog.sar_buffer_slider.value() != value:
            dialog.sar_buffer_slider.blockSignals(True)
            dialog.sar_buffer_slider.setValue(value)
            dialog.sar_buffer_slider.blockSignals(False)
        dialog.sar_buffer_value.setText(
            _tr("Buffer: %+d m") % value if value != 0 else _tr("Buffer: 0 m")
        )

    dialog.sar_buffer_slider.valueChanged.connect(_set_sar_buffer_value)

    lay.addWidget(buffer_panel)
    lay.addStretch(1)

    # Disabling the clicked button (during a worker run) otherwise hands keyboard
    # focus to the next button, which then shows a focus ring as if selected.
    # These are mouse-driven actions, so drop them from the focus chain.
    for _btn in scroll_w.findChildren(QPushButton):
        _btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    scroll.setWidget(scroll_w)
    dialog.sar_results_splitter.addWidget(scroll)
    dialog.sar_results_splitter.setStretchFactor(0, 1)
    dialog.sar_results_splitter.setStretchFactor(1, 0)
    outer.addWidget(dialog.sar_results_splitter)


def setup_radar_page(dialog, page):
    """
    Populate the Radar (SAR) page with a two-tab layout.

    Exposes on dialog:
      sar_layer_combo, sar_date_start, sar_date_end,
      sar_pol_combo, sar_format_combo, sar_index_combo,
      sar_chk_border_noise, sar_chk_terrain, sar_chk_speckle,
      sar_web_view, sar_btn_open_browser, sar_btn_download_csv, sar_btn_filter_dates,
      sar_result_date_combo, sar_btn_preview, sar_btn_download_preview,
      sar_btn_batch_download, sar_render_combo,
      sar_stack, sar_btn_back, sar_btn_next, sar_step_lbl
    """
    page.setObjectName("sarPage")
    page.setStyleSheet("""
        QWidget#sarPage { background-color: #ffffff; }
        QComboBox, QgsMapLayerComboBox {
            combobox-popup: 0;
            background-color: #ffffff;
            color: #212121;
            border: 1px solid #d0d0d0;
            border-radius: 6px;
            padding: 4px 9px;
            font-size: 12px;
        }
        QComboBox:focus, QgsMapLayerComboBox:focus { border: 1.5px solid #1b6b39; }
        QComboBox QAbstractItemView, QgsMapLayerComboBox QAbstractItemView {
            background-color: #ffffff;
            color: #212121;
            border: 1px solid #bdbdbd;
            selection-background-color: #e8f5e9;
            selection-color: #1a1a1a;
            outline: 0;
        }
        QLineEdit {
            background-color: #ffffff;
            color: #212121;
            border: 1px solid #d0d0d0;
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 12px;
        }
        QLineEdit:focus { border: 1.5px solid #1b6b39; }
        QDateEdit {
            background-color: #ffffff;
            color: #212121;
            border: 1px solid #d0d0d0;
            border-radius: 6px;
            padding: 2px 4px 2px 8px;
            font-size: 12px;
        }
        QDateEdit:focus { border: 1.5px solid #1b6b39; }
        QLabel { background: transparent; border: none; }
        QCalendarWidget QWidget {
            background-color: #ffffff;
            color: #212121;
            alternate-background-color: #f5f5f5;
        }
        QCalendarWidget QAbstractItemView {
            background-color: #ffffff;
            color: #212121;
            selection-background-color: #1b6b39;
            selection-color: #ffffff;
        }
        QCalendarWidget QWidget#qt_calendar_navigationbar {
            background-color: #f8f9fa;
            border-bottom: 1px solid #e0e0e0;
        }
        QCalendarWidget QToolButton {
            background-color: transparent;
            color: #212121;
            border: none;
            padding: 2px 6px;
            font-size: 12px;
        }
        QCalendarWidget QToolButton:hover {
            background-color: #e8f5e9;
            border-radius: 4px;
        }
        QCalendarWidget QMenu { background-color: #ffffff; color: #212121; }
        QCalendarWidget QSpinBox {
            background-color: #ffffff;
            color: #212121;
            border: 1px solid #d0d0d0;
            border-radius: 4px;
            padding: 2px 4px;
        }
    """)

    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    tab_bar = QFrame()
    tab_bar.setObjectName("sarTabBar")
    tab_bar.setFixedHeight(40)
    tab_bar.setStyleSheet("""
        QFrame#sarTabBar {
            background-color: #f8f9fa;
            border-bottom: 1px solid #e0e0e0;
        }
    """)
    tab_bar_lay = QHBoxLayout(tab_bar)
    tab_bar_lay.setContentsMargins(6, 0, 6, 0)
    tab_bar_lay.setSpacing(8)

    btn_tab_intro = QPushButton(_tr("Intro"))
    btn_tab_intro.setFixedHeight(40)
    btn_tab_intro.setCursor(Qt.CursorShape.PointingHandCursor)

    btn_tab_inputs = QPushButton(_tr("Inputs"))
    btn_tab_inputs.setFixedHeight(40)
    btn_tab_inputs.setCursor(Qt.CursorShape.PointingHandCursor)

    btn_tab_results = QPushButton(_tr("Results"))
    btn_tab_results.setFixedHeight(40)
    btn_tab_results.setCursor(Qt.CursorShape.PointingHandCursor)

    tab_bar_lay.addWidget(btn_tab_intro)
    tab_bar_lay.addWidget(btn_tab_inputs)
    tab_bar_lay.addWidget(btn_tab_results)
    tab_bar_lay.addStretch(1)

    outer.addWidget(tab_bar)

    stack = QStackedWidget()
    stack.setStyleSheet("QStackedWidget { background: transparent; border: none; }")

    intro_page = QWidget()
    _build_intro_tab(dialog, intro_page)
    stack.addWidget(intro_page)

    inputs_page = QWidget()
    _build_inputs_tab(dialog, inputs_page)
    stack.addWidget(inputs_page)

    results_page = QWidget()
    _build_results_tab(dialog, results_page)
    stack.addWidget(results_page)

    outer.addWidget(stack, 1)
    dialog.sar_stack = stack

    nav_bar = QFrame()
    nav_bar.setObjectName("sarNavBar")
    nav_bar.setFixedHeight(46)
    nav_bar.setStyleSheet("""
        QFrame#sarNavBar {
            background-color: #f8f9fa;
            border-top: 1px solid #e0e0e0;
        }
    """)
    nav_lay = QHBoxLayout(nav_bar)
    nav_lay.setContentsMargins(6, 0, 6, 0)
    nav_lay.setSpacing(8)

    btn_back = QPushButton(_tr("Back"))
    btn_back.setMinimumWidth(90)
    btn_back.setFixedHeight(30)
    btn_back.setStyleSheet(STYLE_BTN_SECONDARY)

    nav_lay.addWidget(btn_back)
    nav_lay.addStretch(1)

    step_lbl = QLabel()
    step_lbl.setStyleSheet("color: #bdbdbd; font-size: 11px; background: transparent;")
    nav_lay.addWidget(step_lbl)

    nav_lay.addStretch(1)

    btn_intro_next = QPushButton(_tr("Next"))
    btn_intro_next.setMinimumWidth(90)
    btn_intro_next.setFixedHeight(30)
    btn_intro_next.setStyleSheet(STYLE_BTN_PRIMARY)
    nav_lay.addWidget(btn_intro_next)

    btn_next = QPushButton(_tr("Run"))
    btn_next.setMinimumWidth(90)
    btn_next.setFixedHeight(30)
    btn_next.setStyleSheet(STYLE_BTN_PRIMARY)
    nav_lay.addWidget(btn_next)
    outer.addWidget(nav_bar)

    dialog.sar_btn_back = btn_back
    dialog.sar_btn_next = btn_next
    dialog.sar_step_lbl = step_lbl

    def _set_tab(index):
        stack.setCurrentIndex(index)
        btn_back.setEnabled(index > 0)
        step_lbl.setText(_tr("Step %d of 3") % (index + 1))
        btn_intro_next.setVisible(index == 0)
        btn_next.setVisible(index == 1)
        btn_tab_intro.setStyleSheet(_TAB_ACTIVE if index == 0 else _TAB_INACTIVE)
        btn_tab_inputs.setStyleSheet(_TAB_ACTIVE if index == 1 else _TAB_INACTIVE)
        btn_tab_results.setStyleSheet(_TAB_ACTIVE if index == 2 else _TAB_INACTIVE)

    dialog.sar_set_tab = _set_tab

    btn_tab_intro.clicked.connect(lambda: _set_tab(0))
    btn_tab_inputs.clicked.connect(lambda: _set_tab(1))
    btn_tab_results.clicked.connect(lambda: _set_tab(2))
    btn_intro_next.clicked.connect(lambda: _set_tab(1))
    btn_back.clicked.connect(
        lambda: _set_tab(stack.currentIndex() - 1) if stack.currentIndex() > 0 else None
    )

    _set_tab(0)
