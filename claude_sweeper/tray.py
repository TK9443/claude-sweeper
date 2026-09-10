from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QCursor, QIcon, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from . import __version__, theme


def _mark(size: int) -> QPixmap:
    for name in ("claude-sweeper-256.png", "claude-sweeper.png", "claude-sweeper-128.png"):
        path = os.path.join(theme.assets_dir(), name)
        if os.path.exists(path):
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                return pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(theme.T["remove"]))
    return pixmap


def _glyph(size: int) -> QPixmap:
    """Black on transparent, which macOS reads as a template and paints white. The colour tile
    cannot serve: a template is built from alpha alone, so it would arrive as a solid block."""
    pixmap = QPixmap(os.path.join(theme.assets_dir(), "tray-template.png"))
    if pixmap.isNull():
        return _mark(size)
    return pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


def tray_icon() -> QIcon:
    template = sys.platform == "darwin"
    icon = QIcon()
    for size in (16, 22, 32, 48, 64):
        icon.addPixmap(_glyph(size) if template else _mark(size))
    icon.setIsMask(template)
    return icon


class SweeperTray(QSystemTrayIcon):
    def __init__(self, window) -> None:
        super().__init__(window)
        self.window = window
        self.menu = QMenu()
        # Left click opens the window, right click the menu. Qt only splits them when no context
        # menu is attached; with one set it hands every click to the menu.
        self.activated.connect(self._on_activated)
        self.setIcon(tray_icon())
        self.setToolTip("Claude Sweeper")
        self._build_menu()

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Context:
            self.menu.popup(QCursor.pos())
        elif reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.window.show_window()

    def notify(self, title: str, message: str) -> None:
        if self.supportsMessages():
            self.showMessage(title, message, tray_icon(), 5000)

    def set_busy(self, busy: bool) -> None:
        self.purge_action.setEnabled(not busy)
        self.check_action.setEnabled(not busy)
        self.purge_action.setText("Working…" if busy else "Remove matching chips")

    def _build_menu(self) -> None:
        header = QAction(f"Claude Sweeper {__version__}", self.menu)
        header.setEnabled(False)
        self.menu.addAction(header)
        self.menu.addSeparator()

        self.purge_action = QAction("Remove matching chips", self.menu)
        self.purge_action.triggered.connect(self.window.purge_now)
        self.menu.addAction(self.purge_action)

        self.check_action = QAction("Count saved chips", self.menu)
        self.check_action.triggered.connect(self.window.check_now)
        self.menu.addAction(self.check_action)

        log_action = QAction("Open the log", self.menu)
        log_action.triggered.connect(self.window.open_log)
        self.menu.addAction(log_action)

        self.menu.addSeparator()
        show = QAction("Show Claude Sweeper", self.menu)
        show.triggered.connect(self.window.show_window)
        self.menu.addAction(show)

        quit_action = QAction("Quit Claude Sweeper", self.menu)
        quit_action.triggered.connect(self.window.quit)
        self.menu.addAction(quit_action)
