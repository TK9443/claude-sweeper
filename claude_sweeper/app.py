from __future__ import annotations

import ctypes
import html
import os
import sys
import time
from collections import Counter

from PySide6.QtCore import QObject, QPoint, QRect, QSettings, QSize, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QLayout, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from . import __version__, engine, theme
from .theme import repolish
from .tray import SweeperTray

PATTERN_SETTING = "titlePattern"
TRAY_WORD = "menu bar" if sys.platform == "darwin" else "tray"


class Worker(QObject):
    """One purge or count, off the UI thread. Quitting Chrome and waiting for it is the slow
    part, and a purge that blocked the window would look like a hang."""

    done = Signal(bool, str)  # deleted, summary

    def __init__(self, delete: bool, quit_chrome: bool, pattern: str) -> None:
        super().__init__()
        self.delete = delete
        self.quit_chrome = quit_chrome
        self.pattern = pattern

    def run(self) -> None:
        relaunch = False
        if self.quit_chrome:
            if not engine.quit_chrome():
                self.done.emit(self.delete, "Chrome did not quit, so nothing was touched.")
                return
            relaunch = True
        code, output = engine.run(self.delete, self.pattern)
        summary = engine.summarise(code, output, self.delete)
        if relaunch:
            engine.relaunch_chrome()
            summary += " Chrome is reopening."
        self.done.emit(self.delete, summary)


class FlowLayout(QLayout):
    """Chips wrap onto new lines as the window narrows; Qt ships no flow layout."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 4) -> None:
        super().__init__(parent)
        self._items = []
        self._gap = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._place(QRect(0, 0, width, 0), move=False)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._place(rect, move=True)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _place(self, rect: QRect, move: bool) -> int:
        x, y, line = rect.x(), rect.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            if line and x + hint.width() > rect.right() + 1:
                x, y, line = rect.x(), y + line + self._gap, 0
            if move:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._gap
            line = max(line, hint.height())
        return y + line - rect.y()


class ElidedLabel(QLabel):
    """One line that shortens with an ellipsis rather than wrapping and growing the foot. The
    whole text stays in the tooltip."""

    def __init__(self) -> None:
        super().__init__()
        self._full = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def set_full_text(self, text: str) -> None:
        self._full = text
        self.setToolTip(text)
        self._elide()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        self.setText(self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideRight, self.width()))


def _when(stamp: str) -> str:
    """Today's runs read as a time; older ones as day, month and time, which is all a log this
    short ever needs."""
    today = time.strftime("%d-%m-%Y")
    if stamp.startswith(today):
        return stamp[len(today) + 1:]
    return f"{stamp[:5]} {stamp[11:]}" if len(stamp) == 16 else stamp


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


class Window(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Claude Sweeper")
        # Narrow enough to tile beside another window on a laptop screen.
        self.setMinimumSize(560, 380)
        self.resize(640, 460)
        self.settings = QSettings("Kalkman", "Claude Sweeper")
        self._thread: QThread | None = None
        self._worker: Worker | None = None
        self._hidden_once = False
        self._busy_text = ""
        self._summary = ""
        self._chrome_open = False
        self._run: engine.Run | None = None
        self._last_purge: engine.Run | None = None
        self.tray: SweeperTray | None = None
        self._build()
        if sys.platform == "win32":
            from . import titlebar
            titlebar.apply_caption(int(self.winId()), theme.T)
        self.refresh()

    # ----- layout ----------------------------------------------------------------------

    def _build(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        top = QFrame()
        top.setProperty("ui", "top")
        top_row = QHBoxLayout(top)
        top_row.setContentsMargins(18, 14, 18, 12)
        top_row.setSpacing(8)
        title = QLabel("Saved agent chips")
        title.setProperty("ui", "title")
        self.state_dot = QFrame()
        self.state_dot.setProperty("ui", "dot")
        self.state_dot.setFixedSize(7, 7)
        self.state_label = QLabel()
        self.state_label.setProperty("ui", "state")
        top_row.addWidget(title)
        top_row.addStretch(1)
        top_row.addWidget(self.state_dot, 0, Qt.AlignmentFlag.AlignVCenter)
        top_row.addWidget(self.state_label)
        layout.addWidget(top)

        bar = QFrame()
        bar.setProperty("ui", "filter")
        bar_row = QHBoxLayout(bar)
        bar_row.setContentsMargins(18, 9, 18, 9)
        bar_row.setSpacing(10)
        label = QLabel("Group titles matching")
        label.setProperty("ui", "muted")
        self.pattern = QLineEdit(str(self.settings.value(PATTERN_SETTING, engine.DEFAULT_PATTERN)))
        self.pattern.setMinimumWidth(170)
        self.pattern.setMaximumWidth(240)
        self.pattern.setToolTip("A case-insensitive regular expression. Saved groups whose title matches are the ones counted and removed.")
        self.pattern.textChanged.connect(self._pattern_changed)
        self.pattern.editingFinished.connect(self._save_pattern)
        label.setBuddy(self.pattern)
        self.counted = QLabel()
        self.counted.setProperty("ui", "muted")
        bar_row.addWidget(label)
        bar_row.addWidget(self.pattern)
        bar_row.addStretch(1)
        bar_row.addWidget(self.counted)
        layout.addWidget(bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        # The table takes focus first, so the window does not open with the pattern field lit
        # up as if it needed attention; Tab still reaches the field next.
        self.scroll.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout.addWidget(self.scroll, 1)

        foot = QFrame()
        foot.setProperty("ui", "foot")
        foot_row = QHBoxLayout(foot)
        foot_row.setContentsMargins(18, 10, 18, 10)
        foot_row.setSpacing(8)
        self.note = ElidedLabel()
        self.note.setProperty("ui", "stamp")
        log_button = QPushButton("Open log")
        log_button.clicked.connect(self.open_log)
        self.count_button = QPushButton("Count")
        self.count_button.clicked.connect(self.check_now)
        self.purge_button = QPushButton("Purge now")
        self.purge_button.setProperty("ui", "primary")
        self.purge_button.clicked.connect(self.purge_now)
        foot_row.addWidget(self.note, 1)
        foot_row.addWidget(log_button)
        foot_row.addWidget(self.count_button)
        foot_row.addWidget(self.purge_button)
        layout.addWidget(foot)
        self.setCentralWidget(root)

        # No menu bar, so macOS gives the window no Cmd+W of its own.
        QShortcut(QKeySequence.StandardKey.Close, self, self.close)

    def _table(self) -> QWidget:
        body = QWidget()
        column = QVBoxLayout(body)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        run = self._run
        if run is None or not run.profiles:
            empty = QLabel(
                "Nothing counted yet. Count reads the saved tab groups in every Chrome profile. "
                "Chrome keeps them locked while it runs, so it will offer to quit Chrome and reopen it."
                if run is None else "No Chrome profile with saved tab groups was found."
            )
            empty.setProperty("ui", "empty")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            column.addStretch(1)
            column.addWidget(empty)
            column.addStretch(2)
            return body
        removed = run.kind == "delete"
        # Red means "the purge button removes this". Chips already gone, or counted for a
        # pattern other than the one in the field, are history, not a promise.
        muted = removed or run.pattern != self.pattern.text()
        column.addWidget(self._row("Profile", "Saved", "Removed" if removed else "Matching", header=True))
        for profile in run.profiles:
            column.addWidget(self._row(profile.name, str(profile.saved), str(profile.matching), profile=profile, muted=muted))
        column.addStretch(1)
        return body

    def _render_table(self) -> None:
        old = self.scroll.takeWidget()
        if old is not None:
            old.deleteLater()
        self.scroll.setWidget(self._table())

    def _row(self, name: str, saved: str, matching: str, header: bool = False,
             profile: engine.Profile | None = None, muted: bool = False) -> QFrame:
        row = QFrame()
        row.setProperty("ui", "thead" if header else "row")
        grid = QGridLayout(row)
        pad = 6 if header else 9
        grid.setContentsMargins(18, pad, 18, pad)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        first = QLabel(name)
        first.setProperty("ui", "th" if header else "")
        grid.addWidget(first, 0, 0)
        for col, text, hit in ((1, saved, False), (2, matching, not header and not muted and matching != "0")):
            cell = QLabel(text)
            cell.setProperty("ui", "th" if header else ("hit" if hit else "num"))
            cell.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            cell.setMinimumWidth(70)
            grid.addWidget(cell, 0, col)
        grid.setColumnStretch(0, 1)
        if profile and profile.titles:
            chips = QWidget()
            chips.setProperty("ui", "plain")
            flow = FlowLayout(chips)
            for title, count in Counter(profile.titles).items():
                # Rich text, because a stylesheet cannot strike a label through. Only the title
                # is struck; the count beside it is a figure, not something removed.
                chip = QLabel(f"<s>{html.escape(title or 'untitled')}</s>" + (f" ×{count}" if count > 1 else ""))
                chip.setTextFormat(Qt.TextFormat.RichText)
                chip.setProperty("ui", "chip-gone" if muted else "chip")
                flow.addWidget(chip)
            grid.addWidget(chips, 1, 0, 1, 3)
        return row

    # ----- state -----------------------------------------------------------------------

    def refresh(self) -> None:
        self._chrome_open = engine.chrome_running()
        self.state_label.setText("Chrome is open, store locked" if self._chrome_open else "Chrome is closed")
        repolish(self.state_dot, state="locked" if self._chrome_open else "free")
        runs = engine.runs(engine.read_log_tail(400))
        self._run = runs[-1] if runs else None
        self._last_purge = next((r for r in reversed(runs) if r.kind == "delete"), None)
        self._pattern_changed()

    def _pending(self) -> int | None:
        """Chips the last count found for the pattern now in the field; None when unknown."""
        run = self._run
        if run and run.kind == "count" and run.pattern == self.pattern.text():
            return run.pending
        return None

    def _pattern_changed(self) -> None:
        valid = engine.valid_pattern(self.pattern.text())
        repolish(self.pattern, state="" if valid else "bad")
        run = self._run
        if not valid:
            self.counted.setText("matches every group")
        elif run is None:
            self.counted.setText("not counted yet")
        else:
            verb = "purged" if run.kind == "delete" else "counted"
            other = "" if run.pattern == self.pattern.text() else f" for “{run.pattern}”"
            self.counted.setText(f"{verb} {_when(run.stamp)}{other}")
        repolish(self.counted, state="" if valid else "bad")
        self._render_table()
        self._update_actions(valid)

    def _save_pattern(self) -> None:
        if engine.valid_pattern(self.pattern.text()):
            self.settings.setValue(PATTERN_SETTING, self.pattern.text())

    def _update_actions(self, valid: bool | None = None) -> None:
        if valid is None:
            valid = engine.valid_pattern(self.pattern.text())
        busy = self._thread is not None
        pending = self._pending()
        if busy:
            text = self._busy_text
        elif pending:
            text = f"Quit Chrome and remove {pending}" if self._chrome_open else f"Remove {pending}"
        elif pending == 0:
            text = "Nothing to remove"
        else:
            text = "Quit Chrome and purge" if self._chrome_open else "Purge now"
        # Red leads only when a current count says what it will remove; until then Count leads,
        # so the user sees what would go before anything goes.
        repolish(self.purge_button, ui="primary" if pending else "")
        repolish(self.count_button, ui="" if pending else "lead")
        self.purge_button.setText(text)
        self.purge_button.setEnabled(valid and not busy and pending != 0)
        self.count_button.setText("Recount" if self._run else "Count")
        self.count_button.setEnabled(valid and not busy)
        self.pattern.setEnabled(not busy)
        if self._summary:
            self.note.set_full_text(self._summary)
        elif self._last_purge:
            last = self._last_purge
            outcome = f"{last.removed} removed" if last.removed else "nothing to remove"
            backup = ", backup kept" if last.backup else ""
            self.note.set_full_text(f"purged {_when(last.stamp)}, {outcome}{backup}")
        else:
            self.note.set_full_text("no purge yet")
        if self.tray:
            self.tray.set_busy(busy)

    def _start(self, delete: bool, quit_chrome: bool) -> None:
        if self._thread is not None:
            return
        self._busy_text = "Quitting Chrome…" if quit_chrome else ("Removing…" if delete else "Counting…")
        self._worker = Worker(delete, quit_chrome, self.pattern.text())
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self._finished)
        self._thread.start()
        self._update_actions()

    def _finished(self, deleted: bool, summary: str) -> None:
        self._thread.quit()
        self._thread.wait()
        self._thread = None
        self._worker = None
        self._summary = summary
        self.refresh()
        if self.tray and deleted:
            self.tray.notify("Claude Sweeper", summary)

    def _confirm_quit_chrome(self, verb: str) -> bool:
        """Chrome holds the store locked, so nothing can even be counted while it is open; the
        choice is quit-and-continue or leave it."""
        box = QMessageBox(self)
        box.setWindowTitle("Claude Sweeper")
        box.setText("Chrome is open, and it keeps the saved groups locked while it runs.")
        box.setInformativeText(f"Quit Chrome, {verb}, then reopen it? Anything unsaved in Chrome is lost when it quits.")
        go = box.addButton(f"Quit Chrome and {verb}", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        return box.clickedButton() is go

    def _go(self, delete: bool) -> None:
        self.show_window()
        if not engine.valid_pattern(self.pattern.text()):
            return
        self._save_pattern()
        quit_chrome = engine.chrome_running()
        if quit_chrome and not self._confirm_quit_chrome("remove the chips" if delete else "count"):
            return
        self._summary = ""
        self._start(delete, quit_chrome)

    def purge_now(self) -> None:
        self._go(True)

    def check_now(self) -> None:
        self._go(False)

    def open_log(self) -> None:
        path = engine.log_path()
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "a", encoding="utf-8").close()
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    # ----- window ----------------------------------------------------------------------

    def show_window(self) -> None:
        if self._thread is None:
            self.refresh()
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.raise_()
        self.activateWindow()
        self.scroll.setFocus()

    def closeEvent(self, event) -> None:
        if self.tray and self.tray.isVisible():
            event.ignore()
            self.hide()
            if not self._hidden_once:
                self._hidden_once = True
                self.tray.notify("Claude Sweeper", f"Still running in the {TRAY_WORD}. Right-click it to remove chips.")
        else:
            event.accept()

    def quit(self) -> None:
        QApplication.instance().quit()


def main() -> None:
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Kalkman.ClaudeSweeper")
    app = QApplication(sys.argv)
    app.setApplicationName("Claude Sweeper")
    app.setApplicationVersion(__version__)
    theme.init_fonts()
    app.setStyleSheet(theme.stylesheet())
    app.setWindowIcon(QIcon(os.path.join(theme.assets_dir(), "claude-sweeper-256.png")))
    window = Window()
    tray = SweeperTray(window)
    if tray.isSystemTrayAvailable():
        tray.show()
        window.tray = tray
        app.setQuitOnLastWindowClosed(False)
    if "--hidden" not in sys.argv[1:] or not tray.isVisible():
        window.show_window()
    sys.exit(app.exec())
