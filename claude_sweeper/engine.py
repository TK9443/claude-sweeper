"""Drives purge/purge.mjs, the one engine for removing saved agent tab-group chips.

The chips live in each profile's Sync Data LevelDB; purge.mjs (Node + classic-level) is the only
thing that writes there, and it is the same file the logon task and the LaunchAgent run. This
module finds Node, tells whether Chrome holds the store, quits and relaunches Chrome around a
purge when asked, and reads the shared log back.
"""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field

WINDOWS = sys.platform == "win32"
MAC = sys.platform == "darwin"


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def purge_script() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "purge", "purge.mjs")
    return os.path.join(_repo_root(), "purge", "purge.mjs")


def log_path() -> str:
    if WINDOWS:
        return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Claude Sweeper", "purge.log")
    return os.path.expanduser("~/Library/Logs/Claude Sweeper/purge.log")


def node_path() -> str | None:
    """A GUI process has no login-shell PATH, so the pinned Node is looked for by location too."""
    found = shutil.which("node")
    if found:
        return found
    candidates = [r"C:\Program Files\nodejs\node.exe"] if WINDOWS else [
        *sorted(glob.glob(os.path.expanduser("~/.local/node-*/bin/node")), reverse=True),
        "/opt/homebrew/bin/node",
        "/usr/local/bin/node",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    if MAC:
        try:
            out = subprocess.run(["zsh", "-lc", "command -v node"], capture_output=True, text=True, timeout=10).stdout.strip()
            if out and os.path.exists(out):
                return out
        except (OSError, subprocess.SubprocessError):
            pass
    return None


def _quiet() -> dict:
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if WINDOWS else {}


def chrome_running() -> bool:
    try:
        if WINDOWS:
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq chrome.exe", "/NH"], capture_output=True, text=True, timeout=15, **_quiet()).stdout
            return "chrome.exe" in out.lower()
        out = subprocess.run(["pgrep", "-x", "Google Chrome"], capture_output=True, text=True, timeout=15).stdout
        return bool(out.strip())
    except (OSError, subprocess.SubprocessError):
        return False


def quit_chrome(timeout: float = 30.0) -> bool:
    """Asks Chrome to close the way the user would; never kills it. A Chrome that will not
    quit (an unsaved form, a 'close all tabs?' prompt) stays open and the purge does not run."""
    try:
        if WINDOWS:
            subprocess.run(["taskkill", "/IM", "chrome.exe"], capture_output=True, timeout=15, **_quiet())
        else:
            subprocess.run(["osascript", "-e", 'tell application "Google Chrome" to quit'], capture_output=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not chrome_running():
            time.sleep(1.0)
            return True
        time.sleep(0.5)
    return False


def relaunch_chrome() -> None:
    try:
        if WINDOWS:
            exe = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Google", "Chrome", "Application", "chrome.exe")
            if os.path.exists(exe):
                subprocess.Popen([exe], **_quiet())
        else:
            subprocess.Popen(["open", "-a", "Google Chrome"])
    except OSError:
        pass


DEFAULT_PATTERN = "claude"


def valid_pattern(pattern: str) -> bool:
    """The purge deletes whatever matches, so a pattern matching an empty title (and so every
    group) is refused here as well as in purge.mjs. Python and JavaScript regular expressions
    agree on everything a group-title pattern plausibly uses."""
    try:
        return re.search(pattern, "", re.IGNORECASE) is None
    except re.error:
        return False


def run(delete: bool, pattern: str = DEFAULT_PATTERN) -> tuple[int, str]:
    node = node_path()
    if not node:
        return 127, "Node was not found; the purge engine needs it."
    if not valid_pattern(pattern):
        return 2, "That title pattern would match every group, so nothing was run."
    args = [node, purge_script(), "--match", pattern, "--log", log_path()]
    if delete:
        args.insert(2, "--delete")
    try:
        done = subprocess.run(args, capture_output=True, text=True, timeout=120, cwd=os.path.dirname(purge_script()), **_quiet())
    except (OSError, subprocess.SubprocessError) as error:
        return 1, str(error)
    return done.returncode, (done.stdout + done.stderr).strip()


_DELETED = re.compile(r"deleted \d+ entities \((\d+) groups")
_MATCHING = re.compile(r"^(\S.*?): (\d+) saved group\(s\), (\d+) matching", re.M)


def summarise(code: int, output: str, deleted: bool) -> str:
    if "Chrome is running" in output:
        return "Chrome is still open, nothing was touched."
    if code == 127 or "Node was not found" in output:
        return "Node was not found, so the purge could not run."
    if code == 2 and "would match every group" in output:
        return output
    if deleted:
        groups = sum(int(m) for m in _DELETED.findall(output))
        profiles = len(_DELETED.findall(output))
        if not groups:
            return "No matching chips were saved anywhere."
        return f"Removed {groups} chip{'s' if groups != 1 else ''} across {profiles} profile{'s' if profiles != 1 else ''}."
    found = [(name, int(n)) for name, _total, n in _MATCHING.findall(output) if int(n)]
    if not found:
        return "No matching chips are saved in any profile."
    total = sum(n for _name, n in found)
    return f"{total} chip{'s' if total != 1 else ''} waiting in {len(found)} profile{'s' if len(found) != 1 else ''}."


@dataclass
class Profile:
    name: str
    saved: int
    matching: int
    titles: list[str] = field(default_factory=list)


@dataclass
class Run:
    kind: str  # "count" or "delete"
    pattern: str
    stamp: str
    profiles: list[Profile] = field(default_factory=list)
    removed: int = 0

    @property
    def pending(self) -> int:
        return sum(p.matching for p in self.profiles)


_STAMP = re.compile(r"^(\d{2}-\d{2}-\d{4} \d{2}:\d{2}):\d{2} ")
_RUN = re.compile(r"^run (count|delete) /(.*)/i$")
_PROFILE = re.compile(r"^(\S.*?): (\d+) saved group\(s\), (\d+) matching")
_TITLE = re.compile(r'^  (".*")  \d+ tab\(s\)$')


def runs(log: str) -> list[Run]:
    """Every run in the log, oldest first, rebuilt from the lines purge.mjs writes. Lines before
    the first `run` marker, and anything unrecognised, are ignored."""
    found: list[Run] = []
    for line in log.splitlines():
        stamp = ""
        match = _STAMP.match(line)
        if match:
            stamp, line = match.group(1), line[match.end():]
        if match := _RUN.match(line):
            found.append(Run(match.group(1), match.group(2), stamp))
            continue
        if not found:
            continue
        run = found[-1]
        if match := _PROFILE.match(line):
            run.profiles.append(Profile(match.group(1), int(match.group(2)), int(match.group(3))))
        elif (match := _TITLE.match(line)) and run.profiles:
            try:
                run.profiles[-1].titles.append(json.loads(match.group(1)))
            except ValueError:
                pass
        elif match := _DELETED.search(line):
            run.removed += int(match.group(1))
    return found


def read_log_tail(lines: int = 60) -> str:
    try:
        with open(log_path(), encoding="utf-8", errors="replace") as handle:
            return "".join(handle.readlines()[-lines:]).rstrip()
    except OSError:
        return ""
