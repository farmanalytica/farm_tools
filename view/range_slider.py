# -*- coding: utf-8 -*-
"""
Compact two-handle horizontal range slider.

Renders a single track with a low handle (left) and a high handle (right).
Value labels float above each handle.  Dragging either handle updates the
corresponding boundary; handles cannot cross.

Compatible with Qt 5 and Qt 6 (accessed through qgis.PyQt).
"""

from qgis.PyQt.QtCore import Qt, pyqtSignal, QRectF, QPointF
from qgis.PyQt.QtGui import QPainter, QColor, QPen, QFont
from qgis.PyQt.QtWidgets import QWidget, QSizePolicy

# ---- Qt5 / Qt6 compat helpers -----------------------------------------------
try:
    _ANTIALIAS = QPainter.RenderHint.Antialiasing
except AttributeError:
    _ANTIALIAS = QPainter.Antialiasing  # type: ignore[attr-defined]

try:
    _NO_PEN = Qt.PenStyle.NoPen
except AttributeError:
    _NO_PEN = Qt.NoPen  # type: ignore[attr-defined]

try:
    _LEFT_BTN = Qt.MouseButton.LeftButton
except AttributeError:
    _LEFT_BTN = Qt.LeftButton  # type: ignore[attr-defined]

try:
    _ALIGN_LABEL = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom
except AttributeError:
    _ALIGN_LABEL = Qt.AlignHCenter | Qt.AlignBottom  # type: ignore[attr-defined]

try:
    _SIZE_EXPANDING = QSizePolicy.Policy.Expanding
    _SIZE_FIXED = QSizePolicy.Policy.Fixed
    _POINTING = Qt.CursorShape.PointingHandCursor
    _SIZEHOR  = Qt.CursorShape.SizeHorCursor
except AttributeError:
    _SIZE_EXPANDING = QSizePolicy.Expanding      # type: ignore[attr-defined]
    _SIZE_FIXED = QSizePolicy.Fixed              # type: ignore[attr-defined]
    _POINTING = Qt.PointingHandCursor            # type: ignore[attr-defined]
    _SIZEHOR  = Qt.SizeHorCursor                # type: ignore[attr-defined]


def _event_x(event) -> float:
    """Return the x coordinate of a QMouseEvent (Qt5 and Qt6 safe)."""
    try:
        return float(event.position().x())
    except AttributeError:
        return float(event.x())


# ---- Colour constants --------------------------------------------------------
_C_TRACK         = QColor("#e0e0e0")
_C_RANGE         = QColor("#1b6b39")
_C_RANGE_HOVER   = QColor("#23924d")   # brighter green on hover / press
_C_HANDLE_BORDER = QColor("#ffffff")
_C_LABEL         = QColor("#616161")


class RangeSlider(QWidget):
    """Horizontal slider with *low* and *high* handles for selecting a range.

    Signals
    -------
    low_changed(float)
        Emitted whenever the low boundary changes.
    high_changed(float)
        Emitted whenever the high boundary changes.

    Properties
    ----------
    low() / high()
        Current boundary values (rounded to *decimals* places).
    set_low(v) / set_high(v)
        Programmatically move a handle, clamped to [minimum, high] or
        [low, maximum] respectively.
    """

    low_changed  = pyqtSignal(float)
    high_changed = pyqtSignal(float)

    # Geometry constants (pixels)
    _LABEL_H = 16   # vertical space for floating value labels
    _HR = 8         # handle radius (normal)
    _HR_HOV = 10    # handle radius when hovered / pressed
    _TH = 4         # track height
    _PAD = 10       # horizontal padding so handles don't clip at edges
    _BOT = 4        # bottom padding

    def __init__(
        self,
        minimum: float,
        maximum: float,
        low: float,
        high: float,
        decimals: int = 2,
        parent=None,
    ):
        super().__init__(parent)
        self._min = float(minimum)
        self._max = float(maximum)
        self._low = float(low)
        self._high = float(high)
        self._decimals = decimals
        self._pressed: str | None = None   # 'low' | 'high' | None
        self._hovered: str | None = None   # 'low' | 'high' | None

        fixed_h = self._LABEL_H + 2 * self._HR_HOV + self._BOT
        self.setMinimumHeight(fixed_h)
        self.setMaximumHeight(fixed_h)
        self.setSizePolicy(_SIZE_EXPANDING, _SIZE_FIXED)
        self.setCursor(_POINTING)
        self.setMouseTracking(True)   # receive mouseMoveEvent without button held
        self.setStyleSheet("background: transparent;")

    # ------------------------------------------------------------------ values

    def low(self) -> float:
        return round(self._low, self._decimals)

    def high(self) -> float:
        return round(self._high, self._decimals)

    def set_low(self, value: float):
        v = max(self._min, min(self._high, float(value)))
        if v != self._low:
            self._low = v
            self.update()
            self.low_changed.emit(self.low())

    def set_high(self, value: float):
        v = min(self._max, max(self._low, float(value)))
        if v != self._high:
            self._high = v
            self.update()
            self.high_changed.emit(self.high())

    # --------------------------------------------------------------- geometry

    def _track_cy(self) -> float:
        return self._LABEL_H + self._HR_HOV

    def _val_to_x(self, val: float) -> float:
        usable = self.width() - 2 * self._PAD
        return self._PAD + (val - self._min) / (self._max - self._min) * usable

    def _x_to_val(self, x: float) -> float:
        usable = self.width() - 2 * self._PAD
        ratio = (x - self._PAD) / usable
        return self._min + ratio * (self._max - self._min)

    def _clamped(self, v: float) -> float:
        return max(self._min, min(self._max, v))

    def _label_rect(self, cx: float, lbl_w: float) -> QRectF:
        """Label rect centered on *cx*, clamped so it can't run past either edge.

        The track has only ``_PAD`` (10px) of clearance, less than half the
        label width (22px) — without clamping, the near-edge label overflows
        the widget and gets clipped by the parent layout.
        """
        x = max(0.0, min(self.width() - lbl_w, cx - lbl_w / 2))
        return QRectF(x, 0, lbl_w, self._LABEL_H)

    # --------------------------------------------------------------- hover

    def _update_hover(self, x: float):
        lx = self._val_to_x(self._low)
        hx = self._val_to_x(self._high)
        dl = abs(x - lx)
        dh = abs(x - hx)
        hit = self._HR_HOV + 4
        if dh <= hit and dh <= dl:
            new = 'high'
        elif dl <= hit:
            new = 'low'
        else:
            new = None
        if new != self._hovered:
            self._hovered = new
            self.setCursor(_SIZEHOR if new is not None else _POINTING)
            self.update()

    # ---------------------------------------------------------------- painting

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(_ANTIALIAS)

        cy  = self._track_cy()
        lx  = self._val_to_x(self._low)
        hx  = self._val_to_x(self._high)
        th  = self._TH
        pad = self._PAD

        # --- background track ---
        painter.setPen(_NO_PEN)
        painter.setBrush(_C_TRACK)
        painter.drawRoundedRect(
            QRectF(pad, cy - th / 2, self.width() - 2 * pad, th), 2, 2
        )

        # --- filled range between handles ---
        painter.setBrush(_C_RANGE)
        painter.drawRoundedRect(QRectF(lx, cy - th / 2, hx - lx, th), 2, 2)

        # --- handles: low first so high renders on top when overlapping ---
        for px, side in [(lx, 'low'), (hx, 'high')]:
            active = self._hovered == side or self._pressed == side
            r      = self._HR_HOV if active else self._HR
            color  = _C_RANGE_HOVER if active else _C_RANGE
            painter.setPen(QPen(_C_HANDLE_BORDER, 2.0))
            painter.setBrush(color)
            painter.drawEllipse(QPointF(px, cy), r, r)

        # --- value labels above handles ---
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(_C_LABEL)

        lo_txt = f"{self.low():+.{self._decimals}f}"
        hi_txt = f"{self.high():+.{self._decimals}f}"
        lbl_w  = 44

        painter.drawText(self._label_rect(lx, lbl_w), _ALIGN_LABEL, lo_txt)
        painter.drawText(self._label_rect(hx, lbl_w), _ALIGN_LABEL, hi_txt)

        painter.end()

    # -------------------------------------------------------- mouse interaction

    def mousePressEvent(self, event):
        if event.button() != _LEFT_BTN:
            return
        x  = _event_x(event)
        lx = self._val_to_x(self._low)
        hx = self._val_to_x(self._high)
        dl = abs(x - lx)
        dh = abs(x - hx)
        hit = self._HR_HOV + 4
        if dh <= hit and dh <= dl:
            self._pressed = 'high'
        elif dl <= hit:
            self._pressed = 'low'
        # else: click outside any handle — ignore

    def mouseMoveEvent(self, event):
        if self._pressed is not None:
            self._move_to(_event_x(event))
        else:
            self._update_hover(_event_x(event))

    def mouseReleaseEvent(self, event):
        self._pressed = None
        self._update_hover(_event_x(event))

    def leaveEvent(self, _event):
        if self._hovered is not None:
            self._hovered = None
            self.setCursor(_POINTING)
            self.update()

    def _move_to(self, x: float):
        val = self._clamped(self._x_to_val(x))
        if self._pressed == 'low':
            new = min(val, self._high)
            if new != self._low:
                self._low = new
                self.update()
                self.low_changed.emit(self.low())
        else:
            new = max(val, self._low)
            if new != self._high:
                self._high = new
                self.update()
                self.high_changed.emit(self.high())
