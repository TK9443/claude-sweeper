# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

The Chrome extension's options page is web. The companion is a PySide6 desktop app for macOS and
Windows styled with Qt stylesheets, so the web platform's conventions are the nearest fit; macOS
and Windows window conventions (Cmd+W, menu-bar template glyph, tray) still bind it.

## Users

People who let an AI agent drive Chrome — Claude in Chrome first, but any agent that works inside
a named tab group. They are developers and power users running agent sessions alongside their own
browsing, often several a day, and they notice the problem only as clutter: a growing row of
saved tab-group chips in the bookmarks bar that they never asked Chrome to keep.

## Product Purpose

Chrome saves every tab group it creates, and no extension API can delete a saved group once it is
closed. Agent sessions create a group each time, so the chips pile up for ever. Claude Sweeper
stops that in two parts: the extension closes an agent's group once it has gone idle, which
deletes the group before Chrome can keep it; the desktop app removes the chips that were saved
anyway, straight from each Chrome profile's sync store, with Chrome closed and a backup taken
first. Success is a bookmarks bar with no agent chips on it, without the user ever thinking about
it.

## Positioning

It is the only route to a saved chip once it exists: the purge edits Chrome's own sync LevelDB,
which no extension can reach. And it is agent-aware: it waits for a group to go quiet rather than
ungrouping on sight, because an agent's group must survive while the agent is still driving it.

## Operating Context

- The extension runs silently in the background; its options page is opened rarely, to switch the
  sweep on or off, set which group titles count as agent groups, and check the last sweep.
- The desktop app lives in the tray (Windows) or menu bar (macOS). The window is opened to purge,
  count saved chips, or read the log. A purge needs Chrome closed, so the app offers to quit
  Chrome, purge and reopen it.
- A purge can also run at login from a scheduled task or LaunchAgent, writing to the same log.

## Capabilities and Constraints

- Group matching is by title pattern (a case-insensitive regular expression, default `claude`).
- Idle window is ten minutes of no tab events in the group; the tabs are closed, not ungrouped,
  because the Claude extension regroups ungrouped tabs at once.
- The purge needs Node (it uses `classic-level` to open LevelDB) and refuses to run while Chrome
  holds the store.
- Chrome only; Chromium forks are not handled.
- Open decision: whether the extension is ever listed on the Chrome Web Store. Today it is
  self-hosted.

## Brand Commitments

- Name: Claude Sweeper (folder and repo `claude-sweeper`). Chosen by the owner 10-09-2026.
- Released free and open source under the MIT licence, as Toby Kalkman's own work.
- British English in all copy.
- No emoji anywhere.

## Evidence on Hand

Real measurements recorded in code comments: the Claude extension regroups an ungrouped tab 9ms
after it leaves its group; a thirty-minute idle window left five chips on one profile. No users,
testimonials, download counts or store ratings exist — none may be invented.

## Product Principles

- Never lose the user's data: back up before deleting, refuse while Chrome is open, never kill
  Chrome.
- Silent when working, legible when asked: the sweep says nothing, but its last result and the
  purge log are always one look away.
- Stay out of the agent's way: a live session must never lose its group.
- Honest about limits: say plainly what cannot be removed without closing Chrome.
