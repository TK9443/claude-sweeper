"""Claude Sweeper's look: a storage inspector over Chrome's own data.

Paper-grey chrome around a white table, ink-black text, and one signal red that means "a purge
removes this": the struck-through chips, the count that will go, the button that does it. Blue is
kept for focus and selection only, so red never has to share its meaning. Light only, because the
window is opened for a minute at a desk, read, and closed.

Widgets opt into a style with a `ui` property, set before the stylesheet applies or re-polished
with `repolish()` after it changes.
"""

from __future__ import annotations

import os
import sys

TOKENS = {
    "ground": "#e9ebe6",
    "sheet": "#fbfbf9",
    "panel": "#ffffff",
    "ink": "#15171a",
    "ink_2": "#555b62",
    "ink_3": "#6b7178",
    "rule": "#dadcd6",
    "rule_strong": "#c3c6bf",
    "select": "#2b50d6",
    "remove": "#c23a22",
    "remove_deep": "#a8301b",
    "remove_wash": "#fbeae6",
    "ok": "#1f7a4d",
}

T: dict[str, str] = dict(TOKENS)

_sans = "Segoe UI" if os.name == "nt" else "Helvetica Neue"
_mono = "Consolas" if os.name == "nt" else "Menlo"


def assets_dir() -> str:
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        candidate = os.path.join(base, "assets")
        if os.path.isdir(candidate):
            return candidate
        bundled = os.path.join(os.path.dirname(sys.executable), "..", "Resources", "assets")
        if os.path.isdir(bundled):
            return os.path.abspath(bundled)
        return candidate
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


def init_fonts() -> None:
    """Registers the bundled Geist faces. A face that will not load leaves the platform default."""
    global _sans, _mono
    from PySide6.QtGui import QFontDatabase

    for filename, role in (("Geist.ttf", "sans"), ("GeistMono.ttf", "mono")):
        handle = QFontDatabase.addApplicationFont(os.path.join(assets_dir(), "fonts", filename))
        families = QFontDatabase.applicationFontFamilies(handle) if handle != -1 else []
        if not families:
            continue
        if role == "sans":
            _sans = families[0]
        else:
            _mono = families[0]


def repolish(widget, **properties) -> None:
    for name, value in properties.items():
        widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def stylesheet() -> str:
    return _TEMPLATE.format(sans=_sans, mono=_mono, **T)


_TEMPLATE = """
QWidget {{ background: {sheet}; color: {ink}; font-family: "{sans}"; font-size: 13px; }}
QWidget[ui="plain"] {{ background: transparent; }}

QFrame[ui="top"] {{ background: {sheet}; border: 0; border-bottom: 1px solid {rule}; }}
QFrame[ui="filter"] {{ background: {panel}; border: 0; border-bottom: 1px solid {rule}; }}
QFrame[ui="foot"] {{ background: {ground}; border: 0; border-top: 1px solid {rule}; }}
QFrame[ui="thead"] {{ background: {sheet}; border: 0; border-bottom: 1px solid {rule}; }}
QFrame[ui="row"] {{ background: {panel}; border: 0; border-bottom: 1px solid {rule}; }}
QFrame[ui="dot"] {{ background: {ok}; border: 0; border-radius: 3px; }}
QFrame[ui="dot"][state="locked"] {{ background: {ink_2}; }}

QLabel {{ background: transparent; color: {ink}; }}
QLabel[ui="title"] {{ font-size: 15px; font-weight: 600; }}
QLabel[ui="state"], QLabel[ui="muted"] {{ color: {ink_2}; font-size: 12px; }}
QLabel[ui="muted"][state="bad"] {{ color: {remove}; }}
QLabel[ui="th"] {{ color: {ink_3}; font-size: 12px; font-weight: 500; }}
QLabel[ui="num"] {{ font-family: "{mono}"; font-size: 12px; }}
QLabel[ui="hit"] {{ font-family: "{mono}"; font-size: 12px; font-weight: 600; color: {remove}; }}
QLabel[ui="chip"] {{
    font-family: "{mono}"; font-size: 11px; color: {remove};
    background: {remove_wash}; border-radius: 4px; padding: 2px 6px;
}}
QLabel[ui="chip-gone"] {{
    font-family: "{mono}"; font-size: 11px; color: {ink_3};
    background: {ground}; border-radius: 4px; padding: 2px 6px;
}}
QLabel[ui="stamp"] {{ font-family: "{mono}"; font-size: 11px; color: {ink_2}; }}
QLabel[ui="empty"] {{ color: {ink_2}; padding: 24px 56px; }}

QLineEdit {{
    background: {panel}; border: 1px solid {rule_strong}; border-radius: 5px; padding: 4px 8px;
    font-family: "{mono}"; font-size: 12px; color: {ink};
    selection-background-color: {select}; selection-color: #ffffff;
}}
QLineEdit:focus {{ border-color: {select}; }}
QLineEdit[state="bad"] {{ border-color: {remove}; }}
QLineEdit:disabled {{ color: {ink_3}; background: {sheet}; }}

QPushButton {{
    background: {panel}; border: 1px solid {rule_strong}; border-radius: 6px;
    padding: 6px 12px; font-weight: 500; color: {ink};
}}
QPushButton:hover {{ border-color: {ink_3}; }}
QPushButton:pressed {{ background: {ground}; }}
QPushButton:disabled {{ color: {ink_3}; background: {sheet}; border-color: {rule}; }}
QPushButton[ui="primary"] {{ background: {remove}; border-color: {remove}; color: #ffffff; }}
QPushButton[ui="primary"]:hover {{ background: {remove_deep}; border-color: {remove_deep}; }}
QPushButton[ui="primary"]:disabled {{ background: {rule}; border-color: {rule}; color: {ink_3}; }}
QPushButton[ui="lead"] {{ background: {ink}; border-color: {ink}; color: {sheet}; }}
QPushButton[ui="lead"]:hover {{ background: #2c3035; border-color: #2c3035; }}
QPushButton[ui="lead"]:disabled {{ background: {rule}; border-color: {rule}; color: {ink_3}; }}
/* Last, so it wins over the filled variants: a 1px blue edge vanished against the red fill. */
QPushButton:focus, QPushButton[ui="primary"]:focus, QPushButton[ui="lead"]:focus {{
    border: 2px solid {select}; padding: 5px 11px;
}}

QScrollArea {{ background: {sheet}; border: 0; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {rule_strong}; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {ink_3}; }}
QScrollBar:horizontal {{ height: 0; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QToolTip {{ background: {ink}; color: {sheet}; border: 0; padding: 5px 8px; }}
QMenu {{ background: {panel}; border: 1px solid {rule_strong}; padding: 4px; }}
QMenu::item {{ padding: 5px 20px; border-radius: 4px; }}
QMenu::item:selected {{ background: {select}; color: #ffffff; }}
QMenu::item:disabled {{ color: {ink_3}; }}
QMenu::separator {{ height: 1px; background: {rule}; margin: 4px 6px; }}
"""
