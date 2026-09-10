# Design

Claude Sweeper looks like a storage inspector over Chrome's own data: figures about what is saved
and what will go, never a settings screen. The desktop window (`claude_sweeper/theme.py`) and the
extension's options page (`extension/options.css`) share one set of tokens.

## Colour

Light only. The window is opened for a minute at a desk, read, and closed.

| Token | Value | Job |
| --- | --- | --- |
| `ground` | `#e9ebe6` | foot bar, muted chip fill, Windows caption |
| `sheet` | `#fbfbf9` | window and page background, table header |
| `panel` | `#ffffff` | table rows, filter bar, fields, buttons |
| `ink` | `#15171a` | text; fill of the leading neutral button |
| `ink_2` | `#555b62` | secondary text, the Chrome lock dot |
| `ink_3` | `#6b7178` | column headings, hints, the switch's off track |
| `rule` / `rule_strong` | `#dadcd6` / `#c3c6bf` | hairlines / control borders |
| `select` | `#2b50d6` | focus, selection, the switch's on state; nothing else |
| `remove` / `remove_deep` / `remove_wash` | `#c23a22` / `#a8301b` / `#fbeae6` | only what a purge removes |
| `ok` | `#1f7a4d` | the dot when Chrome is closed |

Red has one meaning: this will be removed. It appears on struck-through chips, the Matching figure
and the primary button, and only while a current count (same pattern as the field) says so. Chips
already removed, or counted for a different pattern, are muted grey.

## Type

Geist for text, Geist Mono for every figure, pattern, chip and log stamp. Both are bundled
(`assets/fonts/`, `extension/fonts/`, SIL OFL) and never fetched. Window sizes: 15px semibold title,
13px body, 12px labels and figures, 11px chips and stamps. Options page: 20px title, 14px body,
13px ledger, 12px hints and note. Labels are sans even beside mono figures.

## Window

Top bar (title, lock-state dot and words), filter bar (pattern field, "counted HH:MM"), a scrolling
table of profiles with Saved and Matching columns and wrapped chips beneath each name, and a foot
with a two-line stamp and three buttons. 640 x 460 by default, 560 x 380 minimum.

- Before a current count, Count leads as the ink-filled button and purge is plain. With a count
  that found chips, purge becomes red and names the number: "Quit Chrome and remove 10".
- The foot stamp is two fixed lines ("purged 09-09 22:10" / "7 removed, backup kept"), each elided
  rather than wrapped; the full text is in the tooltip.
- Chip titles are struck through; the "×N" count beside them is not.
- Focus is a 2px `select` border on every button.

## Options page

One 520px column: title and one-line purpose, a white panel of two rows (switch, pattern field),
a ledger of the last check in label/figure pairs, and a note on why tabs are closed. A pattern that
matches every group, or does not compile, turns the field border red and says so in the hint; it is
never saved.

## Icon

A flat `remove` red tile with a white pill (a tab-group chip) struck by one horizontal line
(`assets/claude-sweeper.svg`). The macOS menu bar uses the same chip-and-line as a black template
(`assets/tray-template.svg`).
