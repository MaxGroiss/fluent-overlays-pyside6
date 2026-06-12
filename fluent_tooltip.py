"""FluentToolTip -- modern translucent tooltip following Fluent Design.

A custom tooltip that replaces Qt's default with a frameless, translucent
popup drawn via ``QPainter`` -- matching the visual language of
``FluentContextMenu`` but smaller, more translucent, and purpose-built for
short informational text.

Architecture
------------
*   **_ToolTipPopup** -- lightweight top-level ``QWidget`` (ToolTip window
    type, frameless, translucent background).  Handles ``paintEvent`` to
    draw the rounded-rect background, soft drop shadow, and text.
*   **_ToolTipManager** -- singleton ``QObject`` installed as an event filter
    on target widgets.  Manages show delay, auto-hide, and positioning.
*   **FluentToolTip** -- public static API.  Thin facade over the manager.

Usage
-----
::

    from fluent_tooltip import FluentToolTip

    FluentToolTip.set_dark_mode(True)            # optional, default is light
    FluentToolTip.install(my_button, "Save")
    FluentToolTip.set_text(my_button, "New text")
    FluentToolTip.uninstall(my_button)

Features
--------
-   Frameless, translucent, ``QPainter``-drawn rounded rect + soft shadow.
-   Multi-line support (newlines in the text just work).
-   Smart positioning: appears below the cursor, flips above the widget when
    it would run off the bottom of the screen.
-   Show delay + auto-hide, suppresses the native Qt tooltip.
-   Light / dark theme via a single ``set_dark_mode`` call.
-   No external dependencies beyond PySide6 >= 6.7.

License
-------
MIT -- see LICENSE file.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from PySide6.QtCore import QEvent, QObject, QPoint, QRectF, QTimer, Qt
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import QApplication, QWidget

# -- Timing constants --------------------------------------------------------

_SHOW_DELAY_MS = 500
_AUTO_HIDE_MS = 5000


# ---------------------------------------------------------------------------
# Theme definitions (more translucent than the context menu)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class _TooltipTheme:
    """Colour and metric bundle for one theme variant."""

    bg: QColor
    border: QColor
    text_color: QColor
    shadow_color: QColor

    border_radius: int = 6
    shadow_margin: int = 8
    h_padding: int = 10
    v_padding: int = 6
    font_size: int = 12


DARK = _TooltipTheme(
    bg=QColor(38, 40, 44, 230),
    border=QColor(64, 67, 74, 200),
    text_color=QColor(209, 211, 217),
    shadow_color=QColor(0, 0, 0, 80),
)

LIGHT = _TooltipTheme(
    bg=QColor(247, 248, 249, 235),
    border=QColor(209, 211, 217, 200),
    text_color=QColor(0, 0, 0),
    shadow_color=QColor(0, 0, 0, 35),
)


# ---------------------------------------------------------------------------
# _ToolTipPopup -- the translucent popup
# ---------------------------------------------------------------------------

class _ToolTipPopup(QWidget):
    """Frameless translucent popup with QPainter-drawn rounded rect + shadow."""

    def __init__(self, theme: _TooltipTheme) -> None:
        super().__init__(None)
        self.setObjectName("fluentToolTipPopup")
        self._theme: _TooltipTheme = theme
        self._text: str = ""

        self.setWindowFlags(
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_theme(self, theme: _TooltipTheme) -> None:
        """Apply a new theme."""
        self._theme = theme
        self.update()

    def set_text(self, text: str) -> None:
        """Set the display text and recalculate size."""
        self._text = text
        self._recalc_size()
        self.update()

    def reposition(self, global_pos: QPoint, widget: Optional[QWidget] = None) -> None:
        """Place the tooltip near *global_pos*, clamped to screen edges.

        When *widget* is provided the fallback position (when the tooltip
        would go off-screen below) is placed above the widget rather than
        above the cursor, guaranteeing no overlap with the target.
        """
        screen = QApplication.screenAt(global_pos)
        if screen is None:
            screen = QApplication.primaryScreen()
        avail = screen.availableGeometry()

        self._recalc_size()

        # Center horizontally on cursor, below cursor
        x = global_pos.x() - self.width() // 2
        y = global_pos.y()

        # If it would go off the bottom, show above the widget so the
        # tooltip never overlaps the target (which would cause
        # Leave/Enter flicker).
        if y + self.height() > avail.bottom():
            if widget is not None:
                widget_top = widget.mapToGlobal(QPoint(0, 0)).y()
                y = widget_top - self.height() - 4
            else:
                y = global_pos.y() - self.height() - 20

        # Clamp to screen
        if x + self.width() > avail.right():
            x = avail.right() - self.width()
        x = max(x, avail.left())
        y = max(y, avail.top())

        self.move(x, y)

    # -- painting ------------------------------------------------------------

    def paintEvent(self, _event) -> None:  # noqa: N802
        t = self._theme
        m = t.shadow_margin
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Soft drop shadow (concentric rounded rects, quadratic falloff)
        base_a = t.shadow_color.alpha()
        for i in range(m):
            frac = (m - i) / m
            a = int(base_a * frac * frac)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(
                t.shadow_color.red(),
                t.shadow_color.green(),
                t.shadow_color.blue(),
                a,
            ))
            inset = m - i
            rect = QRectF(
                inset, inset + 1,
                self.width() - 2 * inset,
                self.height() - 2 * inset - 1,
            )
            p.drawRoundedRect(
                rect,
                t.border_radius + i * 0.3,
                t.border_radius + i * 0.3,
            )

        # Background
        bg_rect = QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m)
        p.setBrush(t.bg)
        p.setPen(QPen(t.border, 1.0))
        p.drawRoundedRect(bg_rect, t.border_radius, t.border_radius)

        # Text
        font = QFont(p.font())
        font.setPixelSize(t.font_size)
        p.setFont(font)
        p.setPen(t.text_color)
        text_rect = QRectF(
            m + t.h_padding,
            m + t.v_padding,
            self.width() - 2 * m - 2 * t.h_padding,
            self.height() - 2 * m - 2 * t.v_padding,
        )
        p.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._text,
        )
        p.end()

    # -- internals -----------------------------------------------------------

    def _recalc_size(self) -> None:
        t = self._theme
        m = t.shadow_margin
        font = QFont()
        font.setPixelSize(t.font_size)
        fm = QFontMetrics(font)

        # boundingRect handles newlines naturally
        br = fm.boundingRect(
            0, 0, 9999, 9999,
            int(Qt.AlignmentFlag.AlignLeft) | int(Qt.TextFlag.TextDontClip),
            self._text,
        )

        w = br.width() + 2 * t.h_padding + 2 * m
        h = br.height() + 2 * t.v_padding + 2 * m
        self.setFixedSize(w, h)


# ---------------------------------------------------------------------------
# _ToolTipManager -- singleton event-filter that drives show / hide
# ---------------------------------------------------------------------------

class _ToolTipManager(QObject):
    """Singleton that manages tooltip display for all installed widgets."""

    _instance: Optional["_ToolTipManager"] = None

    @classmethod
    def instance(cls) -> "_ToolTipManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        self._texts: Dict[int, str] = {}
        self._popup: Optional[_ToolTipPopup] = None
        self._pending_widget: Optional[QWidget] = None
        self._dark_mode: bool = False

        self._show_timer = QTimer(self)
        self._show_timer.setSingleShot(True)
        self._show_timer.timeout.connect(self._on_show_timeout)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._hide)

    # -- public management API -----------------------------------------------

    def set_dark_mode(self, value: bool) -> None:
        """Switch the theme for all future (and the currently shown) tooltip."""
        self._dark_mode = value
        if self._popup is not None:
            self._popup.set_theme(self._current_theme())

    def install(self, widget: QWidget, text: str) -> None:
        """Install a fluent tooltip on *widget*."""
        widget.setToolTip("")
        self._texts[id(widget)] = text
        widget.installEventFilter(self)
        widget.destroyed.connect(lambda wid=id(widget): self._on_widget_destroyed(wid))

    def set_text(self, widget: QWidget, text: str) -> None:
        """Update the tooltip text for an already-installed *widget*."""
        self._texts[id(widget)] = text

    def uninstall(self, widget: QWidget) -> None:
        """Remove the fluent tooltip from *widget*."""
        widget.removeEventFilter(self)
        self._texts.pop(id(widget), None)
        if self._pending_widget is widget:
            self._show_timer.stop()
            self._pending_widget = None
            self._hide()

    # -- event filter --------------------------------------------------------

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        wid = id(obj)
        if wid not in self._texts:
            return False

        etype = event.type()

        if etype == QEvent.Type.ToolTip:
            # Suppress native tooltip
            return True

        if etype == QEvent.Type.Enter:
            self._pending_widget = obj
            self._show_timer.start(_SHOW_DELAY_MS)
            return False

        if etype == QEvent.Type.Leave:
            self._show_timer.stop()
            self._hide_timer.stop()
            self._pending_widget = None
            self._hide()
            return False

        if etype == QEvent.Type.MouseButtonPress:
            self._show_timer.stop()
            self._hide_timer.stop()
            self._pending_widget = None
            self._hide()
            return False

        return False

    # -- internal ------------------------------------------------------------

    def _on_show_timeout(self) -> None:
        widget = self._pending_widget
        if widget is None:
            return
        text = self._texts.get(id(widget))
        if not text:
            return

        cursor_pos = QCursor.pos()
        popup = self._ensure_popup()
        popup.set_text(text)
        popup.reposition(
            QPoint(cursor_pos.x(), cursor_pos.y() + 24),
            widget=widget if isinstance(widget, QWidget) else None,
        )
        popup.show()

        # Auto-hide after timeout
        self._hide_timer.start(_AUTO_HIDE_MS)

    def _hide(self) -> None:
        if self._popup is not None and self._popup.isVisible():
            self._popup.hide()

    def _ensure_popup(self) -> _ToolTipPopup:
        theme = self._current_theme()
        if self._popup is None:
            self._popup = _ToolTipPopup(theme)
        self._popup.set_theme(theme)
        return self._popup

    def _on_widget_destroyed(self, wid: int) -> None:
        self._texts.pop(wid, None)
        if self._pending_widget is not None and id(self._pending_widget) == wid:
            self._show_timer.stop()
            self._hide_timer.stop()
            self._pending_widget = None
            self._hide()

    def _current_theme(self) -> _TooltipTheme:
        return DARK if self._dark_mode else LIGHT


# ---------------------------------------------------------------------------
# FluentToolTip -- public API
# ---------------------------------------------------------------------------

class FluentToolTip:
    """Modern translucent tooltip -- Fluent Design, fully custom painted.

    This is a static API.  No instance creation needed.

    Example::

        from fluent_tooltip import FluentToolTip

        FluentToolTip.set_dark_mode(True)
        FluentToolTip.install(save_button, "Save")
        FluentToolTip.set_text(save_button, "Save all changes")
        FluentToolTip.uninstall(save_button)
    """

    @staticmethod
    def set_dark_mode(value: bool) -> None:
        """Switch all fluent tooltips between light and dark.

        Args:
            value: ``True`` for dark theme, ``False`` for light.
        """
        _ToolTipManager.instance().set_dark_mode(value)

    @staticmethod
    def install(widget: QWidget, text: str) -> None:
        """Install a fluent tooltip on *widget*.

        Replaces any native Qt tooltip.  The tooltip appears after a short
        hover delay and auto-hides after a few seconds.

        Args:
            widget: Target widget to attach the tooltip to.
            text:   Tooltip text.  Newlines are supported.
        """
        _ToolTipManager.instance().install(widget, text)

    @staticmethod
    def set_text(widget: QWidget, text: str) -> None:
        """Update the tooltip text for an already-installed widget.

        Args:
            widget: Widget that already has a fluent tooltip installed.
            text:   New tooltip text.
        """
        _ToolTipManager.instance().set_text(widget, text)

    @staticmethod
    def uninstall(widget: QWidget) -> None:
        """Remove the fluent tooltip from *widget*.

        Args:
            widget: Widget to remove the tooltip from.
        """
        _ToolTipManager.instance().uninstall(widget)
