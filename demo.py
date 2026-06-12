"""Interactive demo / screenshot gallery for the Fluent overlays.

Run directly::

    python demo.py

Shows both widgets in this repo:

*   **FluentContextMenu** -- right-click the text editor or the coloured
    panel.  Demonstrates icons, shortcuts, checkable items, a radio
    (``exclusive_group``) section, a submenu, and a disabled item.
*   **FluentToolTip** -- hover the buttons on the right to see the custom
    translucent tooltip.

Toggle the *Dark Mode* checkbox to switch every overlay (and the demo
chrome) between light and dark for screenshots.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from fluent_context_menu import DARK, LIGHT, FluentContextMenu, MenuItemDef, svg_to_icon
from fluent_tooltip import FluentToolTip

# ---------------------------------------------------------------------------
# Inline SVG icons (Lucide-style, stroke="currentColor")
# ---------------------------------------------------------------------------

_SVG_CUT = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><line x1="20" y1="4" x2="8.12" y2="15.88"/><line x1="14.47" y1="14.48" x2="20" y2="20"/><line x1="8.12" y1="8.12" x2="12" y2="12"/></svg>'
_SVG_COPY = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>'
_SVG_PASTE = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/></svg>'
_SVG_TRASH = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>'
_SVG_GRID = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>'
_SVG_FORMAT = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>'
_SVG_BOLD = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 4h8a4 4 0 0 1 4 4 4 4 0 0 1-4 4H6z"/><path d="M6 12h9a4 4 0 0 1 4 4 4 4 0 0 1-4 4H6z"/></svg>'
_SVG_ITALIC = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="4" x2="10" y2="4"/><line x1="14" y1="20" x2="5" y2="20"/><line x1="15" y1="4" x2="9" y2="20"/></svg>'


def _icon(svg: str, dark: bool) -> QIcon:
    """Render an SVG string colourised for the current theme."""
    theme = DARK if dark else LIGHT
    return svg_to_icon(svg, size=16, color=theme.icon_color)


# ---------------------------------------------------------------------------
# Demo window
# ---------------------------------------------------------------------------

class DemoWindow(QMainWindow):
    """Showcases FluentContextMenu and FluentToolTip together."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Fluent Overlays - Demo")
        self.resize(940, 600)
        self._dark = False

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Controls
        ctrl = QHBoxLayout()
        self._toggle = QCheckBox("Dark Mode")
        self._toggle.toggled.connect(self._on_theme)
        ctrl.addWidget(self._toggle)
        ctrl.addStretch()
        root.addLayout(ctrl)

        cols = QHBoxLayout()

        # -- Context menu column --------------------------------------------
        grp1 = QGroupBox("FluentContextMenu (right-click)")
        g1 = QVBoxLayout(grp1)
        self._editor = QTextEdit()
        self._editor.setPlaceholderText(
            "Right-click here for the context menu.\n\n"
            "Includes icons, shortcuts, a checkable item, a radio group\n"
            "(View mode: List / Grid / Columns), a submenu, and a\n"
            "disabled item. Toggle dark mode above for screenshots."
        )
        g1.addWidget(self._editor)
        self._panel = QWidget()
        self._panel.setMinimumHeight(90)
        self._panel.setObjectName("demoPanel")
        g1.addWidget(self._panel)
        cols.addWidget(grp1, 3)

        # -- Tooltip column -------------------------------------------------
        grp2 = QGroupBox("FluentToolTip (hover)")
        g2 = QVBoxLayout(grp2)
        g2.setSpacing(10)
        for label, tip in (
            ("Save", "Save all changes\nShortcut: Ctrl+S"),
            ("Export", "Export the current document as PDF"),
            ("Delete", "Permanently delete\nThis cannot be undone"),
        ):
            btn = QPushButton(label)
            FluentToolTip.install(btn, tip)
            g2.addWidget(btn)
        g2.addStretch()
        hint = QLabel("Hover a button and wait ~0.5 s")
        hint.setWordWrap(True)
        g2.addWidget(hint)
        cols.addWidget(grp2, 2)

        root.addLayout(cols)

        self._status = QLabel("Ready - right-click the editor or panel")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._status)

        self._build_menus()
        self._apply_app_theme()

    # -- Menu construction ---------------------------------------------------

    def _build_menus(self) -> None:
        d = self._dark

        self._menu = FluentContextMenu(dark_mode=d)
        self._menu.add_item("Cut", icon=_icon(_SVG_CUT, d), shortcut="Ctrl+X", callback=lambda: self._log("Cut"))
        self._menu.add_item("Copy", icon=_icon(_SVG_COPY, d), shortcut="Ctrl+C", callback=lambda: self._log("Copy"))
        self._menu.add_item("Paste", icon=_icon(_SVG_PASTE, d), shortcut="Ctrl+V", callback=lambda: self._log("Paste"))
        self._menu.add_separator()
        self._wrap_item = self._menu.add_item(
            "Word Wrap", checkable=True, checked=True, callback=lambda: self._log("Word Wrap"),
        )
        self._menu.add_separator()
        # Radio group via exclusive_group
        self._menu.add_item("View: List", icon=_icon(_SVG_GRID, d), checkable=True, exclusive_group="view", callback=lambda: self._log("View List"))
        self._menu.add_item("View: Grid", icon=_icon(_SVG_GRID, d), checkable=True, checked=True, exclusive_group="view", callback=lambda: self._log("View Grid"))
        self._menu.add_item("View: Columns", icon=_icon(_SVG_GRID, d), checkable=True, exclusive_group="view", callback=lambda: self._log("View Columns"))
        self._menu.add_separator()
        fmt = self._menu.add_submenu("Format", icon=_icon(_SVG_FORMAT, d))
        fmt.add_item("Bold", icon=_icon(_SVG_BOLD, d), shortcut="Ctrl+B", callback=lambda: self._log("Bold"))
        fmt.add_item("Italic", icon=_icon(_SVG_ITALIC, d), shortcut="Ctrl+I", callback=lambda: self._log("Italic"))
        self._menu.add_separator()
        self._menu.add_item("Delete", icon=_icon(_SVG_TRASH, d), enabled=False)
        self._menu.action_triggered.connect(self._on_signal)
        self._menu.attach(self._editor)
        self._menu.attach(self._panel)

    def _rebuild_menus(self) -> None:
        self._menu.detach(self._editor)
        self._menu.detach(self._panel)
        self._build_menus()

    def _on_signal(self, text: str, item_def: MenuItemDef) -> None:
        state = f"  [checked={item_def.checked}]" if item_def.checkable else ""
        self._status.setText(f'Triggered: "{text}"{state}')

    # -- Theme switching -----------------------------------------------------

    def _on_theme(self, checked: bool) -> None:
        self._dark = checked
        self._rebuild_menus()
        FluentToolTip.set_dark_mode(checked)
        self._apply_app_theme()

    def _apply_app_theme(self) -> None:
        if self._dark:
            self.setStyleSheet("""
                QMainWindow { background: #1e1e1e; }
                QGroupBox { color: #e4e4e4; border: 1px solid #3d3d3d; border-radius: 8px; margin-top: 12px; padding-top: 16px; font-size: 13px; }
                QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
                QTextEdit { background: #2b2b2b; color: #e4e4e4; border: 1px solid #3d3d3d; border-radius: 6px; padding: 8px; font-size: 13px; selection-background-color: #264f78; }
                QCheckBox { color: #e4e4e4; font-size: 13px; }
                QPushButton { background: #2b2b2b; color: #e4e4e4; border: 1px solid #3d3d3d; border-radius: 6px; padding: 8px 16px; font-size: 13px; }
                QPushButton:hover { background: #3d3d3d; }
                QLabel { color: #888; font-size: 12px; }
                QWidget#demoPanel { background: #2d3250; border-radius: 8px; }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow { background: #f3f3f3; }
                QGroupBox { color: #1a1a1a; border: 1px solid #e0e0e0; border-radius: 8px; margin-top: 12px; padding-top: 16px; font-size: 13px; }
                QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
                QTextEdit { background: #fff; color: #1a1a1a; border: 1px solid #e0e0e0; border-radius: 6px; padding: 8px; font-size: 13px; selection-background-color: #cce4ff; }
                QCheckBox { color: #1a1a1a; font-size: 13px; }
                QPushButton { background: #fff; color: #1a1a1a; border: 1px solid #e0e0e0; border-radius: 6px; padding: 8px 16px; font-size: 13px; }
                QPushButton:hover { background: #ebebeb; }
                QLabel { color: #888; font-size: 12px; }
                QWidget#demoPanel { background: #e0e7ff; border-radius: 8px; }
            """)

    def _log(self, text: str) -> None:
        self._status.setText(f'Callback: "{text}"')


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = DemoWindow()
    window.show()
    sys.exit(app.exec())
