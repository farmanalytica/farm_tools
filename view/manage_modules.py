# -*- coding: utf-8 -*-
"""
"Customize modules" dialog: reorder and show / hide the plugin's modules.

Opened from the welcome hub. Persists choices via :mod:`module_prefs` and calls
an ``on_apply`` callback on Done so the sidebar rail and the welcome grid rebuild
together. Auth is pinned (always shown, never reordered), so it is not listed.
"""

from qgis.PyQt.QtCore import QCoreApplication, QSize, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from . import module_prefs
from .welcome import (
    FARM_GREEN,
    _LOGO_SVGS,
    _MODULES,
    _draw_module_icon,
    _svg_pixmap,
)
from .styles import STYLE_BTN_SECONDARY


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


# Manageable key -> display name, pulled from the hub's module list so the names
# live in a single place.
_LABELS = {entry[0]: entry[1] for entry in _MODULES}


def _module_icon(kind):
    """Same icon a module shows on its hub card, sized for the list rows."""
    if kind in _LOGO_SVGS:
        pix = _svg_pixmap(_LOGO_SVGS[kind], 22)
    else:
        pix = _draw_module_icon(kind, FARM_GREEN, 22)
    return QIcon(pix)


class ManageModulesDialog(QDialog):
    """Reorder (drag) and show/hide (checkbox) modules; apply on Done."""

    def __init__(self, parent=None, on_apply=None):
        super().__init__(parent)
        self._on_apply = on_apply
        self.setWindowTitle(_tr("Customize modules"))
        self.setMinimumWidth(380)
        self.setMinimumHeight(420)
        self._build()
        self._populate()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        hint = QLabel(
            _tr("Drag to reorder, uncheck to hide. "
                "Changes apply to both the sidebar and this welcome page. "
                "GEE Configuration stays pinned.")
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #6b7280; font-size: 11px;")
        lay.addWidget(hint)

        self.list = QListWidget()
        self.list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.list.setIconSize(QSize(22, 22))
        self.list.setStyleSheet("""
            QListWidget {
                background: #ffffff;
                border: 1px solid #e4e7e5;
                border-radius: 8px;
                outline: none;
                padding: 4px;
            }
            QListWidget::item {
                color: #1a1a1a;
                padding: 8px 6px;
                border-radius: 6px;
            }
            QListWidget::item:selected {
                background: #eef6f0;
                color: #1a1a1a;
            }
            QListWidget::item:hover {
                background: #f7fbf8;
            }
        """)
        lay.addWidget(self.list, 1)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.btn_reset = QPushButton(_tr("Reset to default"))
        self.btn_reset.setStyleSheet(STYLE_BTN_SECONDARY)
        self.btn_reset.clicked.connect(self._reset)
        row.addWidget(self.btn_reset)
        row.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(_tr("Done"))
        buttons.accepted.connect(self._apply_and_close)
        row.addWidget(buttons)

        lay.addLayout(row)

    def _populate(self):
        """(Re)fill the list from stored prefs, in order, with check states."""
        self.list.clear()
        hidden = module_prefs.get_hidden()
        for key in module_prefs.get_order():
            name = _LABELS.get(key, key)
            item = QListWidgetItem(_module_icon(key), _tr(name))
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsDragEnabled
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setCheckState(
                Qt.CheckState.Unchecked if key in hidden
                else Qt.CheckState.Checked
            )
            self.list.addItem(item)

    def _reset(self):
        module_prefs.reset()
        self._populate()

    def _apply_and_close(self):
        order, hidden = [], []
        for i in range(self.list.count()):
            item = self.list.item(i)
            key = item.data(Qt.ItemDataRole.UserRole)
            order.append(key)
            if item.checkState() != Qt.CheckState.Checked:
                hidden.append(key)
        module_prefs.set_prefs(order, hidden)
        if callable(self._on_apply):
            self._on_apply()
        self.accept()
