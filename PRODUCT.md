# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

Recorded as web because it is the nearest of the schema's values: the product is a PySide6 desktop
app for macOS and Windows styled with Qt stylesheets. macOS and Windows window conventions
(Cmd+W, menu-bar template glyph, tray) bind it.

## Users

People who let an AI agent drive Chrome — Claude in Chrome first, but any agent that works inside
a named tab group. They are developers and power users running agent sessions alongside their own
browsing, often several a day, and they notice the problem only as clutter: a growing row of
saved tab-group chips in the bookmarks bar that they never asked Chrome to keep.

## Product Purpose

Chrome saves every tab group it creates, and no extension API can delete a saved group once it is
closed. Agent sessions create a group each time, so the chips pile up for ever. Claude Sweeper
removes them straight from each Chrome profile's sync store, with Chrome closed and a backup taken
first. Success is a bookmarks bar with no agent chips on it.

## Positioning

It is the only route to a saved chip once it exists: the purge edits Chrome's own sync LevelDB,
which no extension can reach.

## Operating Context

- The app lives in the tray (Windows) or menu bar (macOS). The window is opened to count saved
  chips, remove them, or read the log. Chrome must be closed for either, so the app offers to quit
  Chrome, do the work and reopen it.
- A purge can also run at login from a scheduled task or LaunchAgent, writing to the same log the
  app reads.

## Capabilities and Constraints

- Group matching is by title pattern (a case-insensitive regular expression, default `claude`).
- The purge needs Node (it uses `classic-level` to open LevelDB) and refuses to run while Chrome
  holds the store.
- Chrome only; Chromium forks are not handled.

## Brand Commitments

- Name: Claude Sweeper (folder and repo `claude-sweeper`). Chosen by the owner 10-09-2026.
- Released free and open source under the MIT licence, as Toby Kalkman's own work.
- British English in all copy.
- No emoji anywhere.

## Evidence on Hand

No users, testimonials, download counts or ratings exist — none may be invented.

## Product Principles

- Never lose the user's data: back up before deleting, refuse while Chrome is open, never kill
  Chrome.
- Show before removing: what a purge will take is visible before the button that takes it.
- Legible when asked: the last result and the purge log are always one look away.
- Honest about limits: say plainly what cannot be removed without closing Chrome.
