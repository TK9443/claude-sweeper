"""Cmd+W (Ctrl+W on Windows) closes the window. There is no menu bar, so nothing binds it for us.

Run: uv run python tests/test_close_shortcut.py
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from claude_sweeper import theme
from claude_sweeper.app import Window

app = QApplication(sys.argv)
theme.init_fonts()
window = Window()
window.show()
window.activateWindow()
app.setActiveWindow(window)  # offscreen windows are inactive, and a WindowShortcut needs focus
app.processEvents()
QTest.keyClick(window, Qt.Key.Key_W, Qt.KeyboardModifier.ControlModifier)
app.processEvents()
assert not window.isVisible(), "Cmd+W did not close the window"
print("ok: Cmd+W closes the window")
