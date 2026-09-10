# Claude Sweeper

Chrome saves every tab group it creates. Close the group and it stays behind as a chip in the
bookmarks bar, and no extension can delete it. AI agents that drive Chrome, Claude in Chrome
among them, open a fresh tab group for every session, so the chips pile up for ever.

Claude Sweeper stops that in two parts.

- **The extension** watches groups whose title matches a pattern (`claude` by default). While an
  agent is using a group it is left alone; once nothing has touched it for ten minutes, its tabs
  are closed, which deletes the group before Chrome can keep it.
- **The desktop app** removes the chips that were saved anyway. It reads each Chrome profile's
  sync store, lists the saved groups that match, and deletes them, with Chrome closed and a backup
  taken first.

It is not affiliated with or endorsed by Anthropic.

## Why the tabs are closed, not ungrouped

Ungrouping a Claude group does not work: the Claude extension notices a tracked tab leaving its
group and regroups it into a new one within milliseconds, so every sweep would mint a fresh chip.
Closing all of a group's tabs in one call is what Chrome's own "Delete group" does, and it is the
only thing that makes the group, and its chip, go away.

## Install

### Extension

1. Open `chrome://extensions` and switch on Developer mode.
2. Choose Load unpacked and select the `extension` folder.
3. Open the extension's options to switch the sweep on or off, change the title pattern, and see
   when it last ran.

### Desktop app

Needs [uv](https://docs.astral.sh/uv/) and Node.js 22 or later on both platforms, and
[Inno Setup 6](https://jrsoftware.org/isinfo.php) on Windows.

- **macOS**: `./build.sh` builds `Claude Sweeper.app`, signs it ad-hoc (set
  `CLAUDE_SWEEPER_SIGN_IDENTITY` to use a real identity), installs it to `/Applications` and
  launches it. `--no-install` stops after the build; `--no-pin` leaves the Dock alone.
- **Windows**: `install.ps1` builds the installer and installs per user, with Start Menu and
  desktop shortcuts. `-NoLaunch` skips starting it afterwards.

The app lives in the menu bar (macOS) or the notification area (Windows). Its window shows each
profile's saved groups, the ones matching your pattern struck through, and a button that says
exactly how many it will remove. Chrome holds the store locked while it runs, so the app offers to
quit Chrome, do the work, and reopen it. Start it with `--hidden` to go straight to the tray.

## The purge on its own

The engine is a single Node script and can run without the app, for example at login:

```sh
cd purge && npm ci
node purge.mjs                      # dry run: list what would go
node purge.mjs --delete             # remove matching saved groups
node purge.mjs --match 'claude|codex' --delete
node purge.mjs --profile "/path/to/Chrome/Profile 1"
node purge.mjs --delete --log ~/Library/Logs/Claude\ Sweeper/purge.log
```

Its safeguards:

- It refuses to run while Chrome is open, because a half-written store is a corrupt profile.
- Before deleting, it copies each profile's store to `~/Library/Application Support/Claude Sweeper/backups`
  (macOS) or `%LOCALAPPDATA%\Claude Sweeper\backups` (Windows). Copies older than fourteen days are
  removed at the start of the next deleting run.
- A pattern that would match an empty title, and so every group, is refused. The extension and the
  app apply the same rule.

To run it at login, point a LaunchAgent (macOS) or a scheduled task (Windows) at `node purge.mjs
--delete --log <file>`. The app reads the same log, so a purge that ran unseen shows up in its
window.

## Tests

```sh
node tests/sweep.test.mjs
uv run python tests/test_close_shortcut.py
```

## Licence

[MIT](LICENSE). The bundled Geist and Geist Mono fonts are under the SIL Open Font License; see
`assets/fonts/OFL.txt`.
