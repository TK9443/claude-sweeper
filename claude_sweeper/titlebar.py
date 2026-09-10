"""Native title-bar colouring for the window on Windows 11.

Windows paints the ACTIVE window's native caption in the user's accent colour when "Show accent
colour on title bars and window borders" is on (HKCU\\Software\\Microsoft\\Windows\\DWM
ColorPrevalence), so a window can look right unfocused and turn accent-coloured the moment it gains
focus. DWMWA_CAPTION_COLOR and its neighbours (Windows 11 22H2+) are the documented opt-out.
"""

from __future__ import annotations

import sys

DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36
DWMWA_USE_IMMERSIVE_DARK_MODE = 20


def _colorref(hex_colour: str) -> int:
    """"#RRGGBB" -> COLORREF (0x00BBGGRR), the byte order DWM's colour attributes expect."""
    value = hex_colour.lstrip("#")
    r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    return (b << 16) | (g << 8) | r


def apply_caption(hwnd: int, tokens: dict) -> None:
    """Paints hwnd's caption with the paper-grey chrome, ink and rule from `tokens`, and pins the
    light caption theme to match. Cosmetic only: any failure (older Windows, missing dwmapi, a bad
    hwnd) is swallowed so the window still opens."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        dwmapi = ctypes.windll.dwmapi
        light = ctypes.c_int(0)
        dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(light), ctypes.sizeof(light))
        for attribute, name in ((DWMWA_CAPTION_COLOR, "ground"), (DWMWA_TEXT_COLOR, "ink"), (DWMWA_BORDER_COLOR, "rule")):
            value = ctypes.c_int(_colorref(tokens[name]))
            dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass
