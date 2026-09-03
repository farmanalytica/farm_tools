# -*- coding: utf-8 -*-
"""
Module icons for the hub cards and the Customize dialog.

A module either ships a brand logo (rendered from ``assets/``) or gets a line
icon drawn here. Both the welcome hub and the Customize list ask for the same
icon, so neither has to know how the other draws it — and neither has to import
the other.
"""

from qgis.PyQt.QtCore import QPoint, QRect, Qt
from qgis.PyQt.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

from .module_catalog import MODULES
from .styles import render_svg_pixmap, scaled_pixmap


LOGO_SVGS = {
    module.key: module.logo_svg for module in MODULES if module.logo_svg
}


def svg_pixmap(filename: str, size: int) -> QPixmap:
    """An assets/ SVG as a square pixmap; blank when the asset is unusable."""
    pixmap = render_svg_pixmap(filename, size)
    if pixmap is not None:
        return pixmap
    return scaled_pixmap(size, size)


def draw_module_icon(kind: str, color: str, size: int = 30) -> QPixmap:
    """Render a crisp line icon for ``kind`` at ``size`` px.

    Recipes mirror ``Sidebar._draw_icon`` (drawn in a 20-unit space) so a card's
    icon matches its sidebar button; the painter is scaled to ``size``.
    """
    pix = scaled_pixmap(size, size)

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
    elif kind == "mzones":
        # Management zones — a field outline split into zones, one filled.
        painter.setPen(pen)
        painter.drawRoundedRect(QRect(3, 4, 14, 12), 2, 2)
        split = QPainterPath()
        split.moveTo(3, 9)
        split.cubicTo(7, 7.5, 9, 11, 12, 9.5)
        split.cubicTo(14, 8.5, 15.5, 9, 17, 8.5)
        painter.drawPath(split)
        painter.drawLine(QPoint(10, 10), QPoint(10, 16))
        painter.fillRect(QRect(11, 11, 5, 4), QColor(color))
    elif kind == "car":
        # Registered land parcel — an irregular closed boundary with a corner
        # marker, evoking a cadastral property polygon.
        painter.setPen(pen)
        parcel = QPainterPath()
        parcel.moveTo(4, 6)
        parcel.lineTo(12, 3)
        parcel.lineTo(17, 9)
        parcel.lineTo(14, 17)
        parcel.lineTo(5, 15)
        parcel.closeSubpath()
        painter.drawPath(parcel)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawEllipse(QRect(11, 2, 3, 3))
    else:
        painter.setPen(pen)
        painter.drawLine(10, 3, 10, 12)
        painter.drawLine(6, 9, 10, 13)
        painter.drawLine(14, 9, 10, 13)
        painter.drawLine(5, 16, 15, 16)

    painter.end()
    return pix
