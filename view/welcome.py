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

import os

from qgis.PyQt.QtCore import (
    QCoreApplication,
    QMimeData,
    QPoint,
    QRect,
    QSize,
    Qt,
)
from qgis.PyQt.QtGui import QDrag
from qgis.PyQt.QtWidgets import (
    QApplication,
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

from . import module_prefs
from .module_catalog import AUTH_KEY, FARM_GREEN
from .module_icons import LOGO_SVGS, draw_module_icon, svg_pixmap
from .module_prefs import hidden_modules, needs_auth_entry, visible_modules
from .styles import STYLE_BTN_SECONDARY, STYLE_INPUT_READONLY, STYLE_STATUS_PILL

# Drag-and-drop mime type carrying a dragged module's key between hub cards.
_MODULE_MIME = "application/x-farm-module"


def _tr(text):
    return QCoreApplication.translate("RAVI", text)

# Plugin assets/ dir (welcome.py lives in view/, so go up one level).
_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")

# Module kinds that carry their own brand logo (SVG) instead of a drawn line icon.



# External links (mirrors ui/intro.html).
_URL_CAIO = "https://www.linkedin.com/in/caioarantes/"
_URL_LUCAS = "https://www.linkedin.com/in/lucas-rios-do-amaral-bb302449/"
_URL_FARM = "https://farmanalytica.com.br"
_URL_SITE = "https://www.farmtools.org"
_URL_MATEUS = "https://www.linkedin.com/in/mateuspinto/"
_URL_AGRIGEE = "https://github.com/mateuspinto/AgriGEE.lite"
_LINK_STYLE = "color:#1b6b39; font-weight:bold; text-decoration:none;"

class CardGridLayout(QLayout):
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
        # Cap the stretch so wide viewports don't inflate cards into short-text,
        # tall-empty tiles; centre the leftover width so the grid stays balanced.
        card_w = min(card_w, _CARD_MAX_WIDTH)
        row_w = n_cols * card_w + (n_cols - 1) * spacing
        x_offset = max(0, (available_w - row_w) // 2)

        for i, item in enumerate(self._items):
            col = i % n_cols
            row = i // n_cols
            x = effective.x() + x_offset + col * (card_w + spacing)
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
    layout / enclosing QScrollArea, so a ``CardGridLayout`` grid's true multi-row
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




_CARD_WIDTH = 248
# Cap on how wide a card may stretch to fill a row. Without it, a wide viewport
# inflates each card far beyond its text, so the blurb wraps to 1–2 lines and
# leaves tall empty space under it. Capping keeps cards near their natural width
# (blurb fills the height) and lets more columns pack in — a denser grid.
_CARD_MAX_WIDTH = 272
# Tall enough for a one-line title plus a four-line wrapped description
# (translated blurbs, e.g. pt_BR, run longer than the English source).
_CARD_HEIGHT = 116


class _ModuleCard(QPushButton):
    """Hub card that navigates on click and can be dragged to reorder.

    Auth is pinned (``key == 'auth'``) and never starts a drag. A drag begins
    once the pointer moves past the platform drag distance with the left button
    held; starting the QDrag suppresses the click, so a plain click still
    navigates."""

    def __init__(self, key, draggable=True, parent=None):
        super().__init__(parent)
        self.module_key = key
        self._draggable = draggable
        self._press_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self._draggable
                and self._press_pos is not None
                and (event.buttons() & Qt.MouseButton.LeftButton)
                and (event.pos() - self._press_pos).manhattanLength()
                >= QApplication.startDragDistance()):
            self._press_pos = None
            self.setDown(False)
            drag = QDrag(self)
            mime = QMimeData()
            mime.setData(_MODULE_MIME, self.module_key.encode("utf-8"))
            drag.setMimeData(mime)
            drag.setPixmap(self.grab())
            drag.setHotSpot(event.pos())
            drag.exec(Qt.DropAction.MoveAction)
            return
        super().mouseMoveEvent(event)


class _ReorderGridHost(_HeightForWidthWidget):
    """Grid container that accepts dropped module cards to reorder them."""

    def __init__(self, on_drop, parent=None):
        super().__init__(parent)
        self._on_drop = on_drop
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(_MODULE_MIME):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(_MODULE_MIME):
            event.acceptProposedAction()

    def dropEvent(self, event):
        md = event.mimeData()
        if not md.hasFormat(_MODULE_MIME):
            return
        key = bytes(md.data(_MODULE_MIME)).decode("utf-8")
        # Qt6 (QGIS 4) exposes position(); Qt5 uses pos().
        point = (event.position().toPoint()
                 if hasattr(event, "position") else event.pos())
        self._on_drop(key, point)
        event.acceptProposedAction()


def _persist_visible_order(new_visible):
    """Write ``new_visible`` back as the order of the visible slots only.

    Hidden modules keep their absolute positions; the permutation applies just
    to the slots the visible modules occupy, so dragging never disturbs the
    hidden set's ordering."""
    full = module_prefs.get_order()
    hidden = module_prefs.get_hidden()
    it = iter(new_visible)
    result = []
    for key in full:
        if key in hidden:
            result.append(key)
        else:
            result.append(next(it, key))
    module_prefs.set_prefs(result, hidden)


def _reorder_from_drop(dialog, key, point):
    """Reorder visible module cards after a drag-drop at ``point`` (host coords)."""
    grid = getattr(dialog, "_module_grid", None)
    if grid is None:
        return
    keys, target = [], None
    for i in range(grid.count()):
        widget = grid.itemAt(i).widget()
        if not isinstance(widget, _ModuleCard) or widget.module_key == AUTH_KEY:
            continue
        keys.append(widget.module_key)
        rect = widget.geometry()
        if (target is None
                and point.y() <= rect.bottom()
                and point.x() < rect.center().x()):
            target = len(keys) - 1
    if key not in keys:
        return
    if target is None:
        target = len(keys)
    src = keys.index(key)
    if src < target:
        target -= 1
    new_visible = [k for k in keys if k != key]
    new_visible.insert(target, key)
    if new_visible == keys:
        return
    _persist_visible_order(new_visible)
    refresh = getattr(dialog, "refresh_modules", None)
    if callable(refresh):
        refresh()


def _build_module_card(dialog, module):
    """One clickable card. The whole card is a button that navigates on click."""
    kind, name, desc = module.key, module.name, module.description
    card = _ModuleCard(kind, draggable=(kind != AUTH_KEY))
    card.setObjectName("moduleCard")
    card.setCursor(Qt.CursorShape.PointingHandCursor)
    card.setMinimumWidth(_CARD_WIDTH)
    card.setFixedHeight(_CARD_HEIGHT)
    card.setToolTip(
        _tr(name) if kind == "auth"
        else _tr("{0} — drag to reorder").format(_tr(name))
    )
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
    if kind in LOGO_SVGS:
        # Brand logo: render bigger to fill the tile, on a neutral white tile so
        # the logo's own colours read cleanly.
        icon_tile.setStyleSheet("background-color: #ffffff; border-radius: 9px;")
        icon_tile.setPixmap(svg_pixmap(LOGO_SVGS[kind], 30))
    else:
        icon_tile.setStyleSheet("background-color: #e8f5e9; border-radius: 9px;")
        icon_tile.setPixmap(draw_module_icon(kind, FARM_GREEN, 20))
    lay.addWidget(icon_tile, 0, Qt.AlignmentFlag.AlignTop)

    text_col = QVBoxLayout()
    text_col.setContentsMargins(0, 0, 0, 0)
    text_col.setSpacing(2)

    title = QLabel(_tr(name))
    title.setStyleSheet("color: #1a1a1a; font-size: 13px; font-weight: bold;")
    title.setWordWrap(True)

    if not module.needs_gee:
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
    def _navigate(_checked=False, attr=module.nav_attr):
        handler = getattr(dialog, attr, None)
        if callable(handler):
            handler()

    card.clicked.connect(_navigate)
    return card


def _build_teaser_card(dialog, module):
    """A demoted "More tools" card: greyed, shows a ``+ Add`` affordance.

    The module is included in this plugin but hidden. Clicking the card un-hides
    it via :mod:`module_prefs` and triggers ``dialog.refresh_modules()`` so the
    card promotes into the active grid (and the sidebar rail) immediately.
    """
    kind, name, desc = module.key, module.name, module.description
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
    if kind in LOGO_SVGS:
        icon_tile.setPixmap(svg_pixmap(LOGO_SVGS[kind], 30))
    else:
        icon_tile.setPixmap(draw_module_icon(kind, "#9aa0a6", 20))
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
    dialog.folder_input.setStyleSheet(STYLE_INPUT_READONLY)
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
    dialog.welcome_auth_badge.setStyleSheet(STYLE_STATUS_PILL)
    # No-login-only build: nothing to sign in for, so hide the status pill.
    dialog.welcome_auth_badge.setVisible(needs_auth_entry())
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

    grid_host = _ReorderGridHost(
        lambda key, point: _reorder_from_drop(dialog, key, point)
    )
    grid_host.setStyleSheet("background: transparent;")
    grid = CardGridLayout(grid_host, margin=0, spacing=12)
    # Kept on the dialog so rebuild_module_grid() can repopulate after the user
    # reorders (drag here or in the Customize dialog) or hides modules.
    dialog._module_grid = grid
    dialog._module_grid_host = grid_host
    for module in visible_modules():
        grid.addWidget(_build_module_card(dialog, module))
    outer.addWidget(grid_host)

    outer.addWidget(_build_teaser_section(dialog))

    outer.addSpacing(16)
    outer.addWidget(_build_folder_section(dialog))
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
    grid = CardGridLayout(grid_host, margin=0, spacing=12)
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
    hidden = hidden_modules()
    for module in hidden:
        grid.addWidget(_build_teaser_card(dialog, module))
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
    for module in visible_modules():
        grid.addWidget(_build_module_card(dialog, module))
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
        badge.setVisible(needs_auth_entry())


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
