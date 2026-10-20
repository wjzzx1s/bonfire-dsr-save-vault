"""Custom-painted widgets that give Bonfire its character."""
from __future__ import annotations

import math
import random
from typing import ClassVar

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from .theme import PALETTE, tracking_font


class Emblem(QWidget):
    """A small hand-painted bonfire sigil."""

    def __init__(self, size: int = 54, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        s = w / 56.0

        glow = QRadialGradient(QPointF(28 * s, 34 * s), 26 * s)
        glow.setColorAt(0.0, QColor(201, 96, 58, 70))
        glow.setColorAt(1.0, QColor(201, 96, 58, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QRectF(2 * s, 8 * s, 52 * s, 48 * s))

        ring = QPen(QColor(PALETTE["GOLD_DIM"]))
        ring.setWidthF(1.1)
        p.setPen(ring)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(2.5 * s, 2.5 * s, 51 * s, 51 * s))

        path = QPainterPath()
        path.moveTo(28 * s, 9 * s)
        path.cubicTo(34 * s, 19 * s, 40 * s, 24 * s, 38 * s, 34 * s)
        path.cubicTo(37 * s, 43 * s, 33 * s, 47 * s, 28 * s, 47 * s)
        path.cubicTo(22 * s, 47 * s, 17 * s, 42 * s, 18 * s, 34 * s)
        path.cubicTo(19 * s, 27 * s, 24 * s, 23 * s, 25 * s, 16 * s)
        path.cubicTo(27 * s, 22 * s, 30 * s, 25 * s, 31 * s, 29 * s)
        path.cubicTo(33 * s, 24 * s, 33 * s, 15 * s, 28 * s, 9 * s)

        fire = QLinearGradient(0, 8 * s, 0, 48 * s)
        fire.setColorAt(0.0, QColor("#f0d7a4"))
        fire.setColorAt(0.45, QColor(PALETTE["GOLD"]))
        fire.setColorAt(1.0, QColor(PALETTE["EMBER"]))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fire)
        p.drawPath(path)

        p.setBrush(QColor(255, 240, 210, 180))
        p.drawEllipse(QRectF(25.5 * s, 32 * s, 5 * s, 8 * s))


class EmberHeader(QWidget):
    """Header artwork: a warm gradient with slow drifting embers."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(112)
        rng = random.Random(7)
        self._embers = [
            {
                "x": rng.uniform(0.03, 0.98),
                "y": rng.uniform(0.25, 1.0),
                "r": rng.uniform(0.7, 2.1),
                "speed": rng.uniform(0.06, 0.24),
                "phase": rng.uniform(0, math.tau),
            }
            for _ in range(26)
        ]
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(70)

    def _step(self) -> None:
        for ember in self._embers:
            ember["y"] -= ember["speed"] / 112.0
            ember["phase"] += 0.06
            if ember["y"] < 0.16:
                ember["y"] = 0.98
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        base = QLinearGradient(0, 0, 0, h)
        base.setColorAt(0.0, QColor("#191510"))
        base.setColorAt(1.0, QColor(PALETTE["BG"]))
        p.fillRect(self.rect(), base)

        glow = QRadialGradient(QPointF(w * 0.13, h * 0.95), max(260, w * 0.32))
        glow.setColorAt(0.0, QColor(201, 96, 58, 48))
        glow.setColorAt(0.55, QColor(201, 96, 58, 14))
        glow.setColorAt(1.0, QColor(201, 96, 58, 0))
        p.fillRect(self.rect(), glow)

        for ember in self._embers:
            alpha = int(28 + 55 * (0.5 + 0.5 * math.sin(ember["phase"])))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(214, 150, 92, alpha))
            x = ember["x"] * w
            y = ember["y"] * h
            p.drawEllipse(QPointF(x, y), ember["r"], ember["r"])

        p.setPen(QPen(QColor(201, 164, 95, 40), 1))
        p.drawLine(0, h - 1, w, h - 1)


class StatusChip(QLabel):
    def __init__(self, text: str = "", tone: str = "muted", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Chip")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(tracking_font(6, 1.2))
        self.set_state(text, tone)

    def set_state(self, text: str, tone: str = "muted") -> None:
        self.setText(text.upper())
        self.setProperty("tone", tone)
        self.style().unpolish(self)
        self.style().polish(self)
        self.updateGeometry()


class Switch(QAbstractButton):
    """An animated iOS-style switch that fits the dark theme."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(44, 24)
        self._knob = 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def _get_knob(self) -> float:
        return self._knob

    def _set_knob(self, value: float) -> None:
        self._knob = value
        self.update()

    knob = Property(float, _get_knob, _set_knob)

    def setChecked(self, checked: bool) -> None:
        self._knob = 1.0 if checked else 0.0
        super().setChecked(checked)
        self._knob = 1.0 if checked else 0.0
        self.update()

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._knob)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(1, 3, self.width() - 2, self.height() - 6)
        p.setPen(Qt.PenStyle.NoPen)
        if self.isChecked():
            p.setBrush(QColor(PALETTE["GOLD"]))
        else:
            p.setBrush(QColor("#332d22"))
        p.drawRoundedRect(track, track.height() / 2, track.height() / 2)

        diameter = self.height() - 8
        x = 4 + self._knob * (self.width() - diameter - 8)
        p.setBrush(QColor("#f4ead2" if self.isChecked() else "#8c8270"))
        p.drawEllipse(QRectF(x, 4, diameter, diameter))


class ElidedLabel(QLabel):
    """A label that ellipsises its text instead of stretching the layout."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._full_text = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(40)

    def setText(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        super().setText(text)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setFont(self.font())
        p.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        metrics = QFontMetrics(self.font())
        text = metrics.elidedText(self._full_text, Qt.TextElideMode.ElideMiddle, max(10, self.width() - 2))
        p.drawText(self.rect(), int(self.alignment()), text)


class KindBadgeDelegate(QStyledItemDelegate):
    """Paints the snapshot type as a coloured pill, plus a pin diamond."""

    COLORS: ClassVar[dict[str, tuple[str, str]]] = {
        "auto": ("#242a2c", "#9fb4bd"),
        "manual": ("#332b1c", "#d9b878"),
        "boss": ("#3a2118", "#e39267"),
        "pre-restore": ("#22302a", "#93b79d"),
    }

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        hint = super().sizeHint(option, index)
        return QSize(hint.width(), 40)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        info = index.data(Qt.ItemDataRole.UserRole) or {}
        kind = str(info.get("kind", "manual"))
        label = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        bg, fg = self.COLORS.get(kind, self.COLORS["manual"])

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont(option.font)
        font.setPointSizeF(7.6)
        font.setWeight(QFont.Weight.DemiBold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.5)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        width = metrics.horizontalAdvance(label.upper()) + 18
        pill = QRectF(option.rect.left() + 8, option.rect.center().y() - 9, width, 19)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(bg))
        painter.drawRoundedRect(pill, 9.5, 9.5)
        painter.setPen(QColor(fg))
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, label.upper())

        if info.get("pinned"):
            cx = pill.right() + 10
            cy = option.rect.center().y()
            diamond = QPainterPath()
            diamond.moveTo(cx, cy - 4)
            diamond.lineTo(cx + 4, cy)
            diamond.lineTo(cx, cy + 4)
            diamond.lineTo(cx - 4, cy)
            diamond.closeSubpath()
            painter.setBrush(QColor(PALETTE["GOLD"]))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(diamond)
        painter.restore()


class Toast(QFrame):
    """Transient status message floating over the bottom of the window."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        self.label = QLabel("")
        self.label.setFont(tracking_font(9, 0.2, bold=False))
        layout.addWidget(self.label)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.hide()

    def show_message(self, text: str, tone: str = "gold", msec: int = 3600) -> None:
        self.label.setText(text)
        self.setProperty("tone", tone)
        self.style().unpolish(self)
        self.style().polish(self)
        self.adjustSize()
        parent = self.parentWidget()
        if parent:
            x = (parent.width() - self.width()) // 2
            y = parent.height() - self.height() - 120
            self.move(max(12, x), max(12, y))
        self.show()
        self.raise_()
        self._timer.start(msec)


class EmptyVault(QWidget):
    """Friendly explanation shown when no snapshots exist yet."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)

        row = QHBoxLayout()
        row.addStretch(1)
        row.setSpacing(16)

        sigil = QLabel("◇")
        sigil.setFont(QFont("Noto Serif", 30))
        sigil.setStyleSheet(f"color: {PALETTE['GOLD_DIM']};")
        sigil.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(sigil, 0, Qt.AlignmentFlag.AlignTop)

        stack = QVBoxLayout()
        stack.setContentsMargins(0, 3, 0, 0)
        stack.setSpacing(5)
        self.title = QLabel("The vault is empty")
        self.title.setObjectName("EmptyTitle")
        self.subtitle = QLabel("Take your first snapshot — the fire remembers.")
        self.subtitle.setObjectName("Small")
        stack.addWidget(self.title)
        stack.addWidget(self.subtitle)
        row.addLayout(stack)
        row.addStretch(1)

        outer.addLayout(row)
        outer.addStretch(1)

    def set_linked(self, linked: bool) -> None:
        if linked:
            self.title.setText("The vault is empty")
            self.subtitle.setText("Take your first snapshot — the fire remembers.")
        else:
            self.title.setText("No save linked")
            self.subtitle.setText("Find DRAKS0005.sl2, then take your first snapshot.")
