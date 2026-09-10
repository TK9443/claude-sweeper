const AUTO_KEY = 'autoUngroup';
const SEEN_KEY = 'lastSeen';
const STATUS_KEY = 'lastSweep';
const PATTERN_KEY = 'titlePattern';
const DEFAULT_PATTERN = 'claude';

// Chrome saves every group it creates and no extension API can remove a saved one, so
// the chip has to go while the group still exists: emptying a group DELETES it, chip
// and all, where merely closing it leaves the chip behind forever.
//
// ⚠ Emptying it by UNGROUPING does not work against a Claude group. The Claude extension
// keeps every group it made in its own storage and, the instant a tracked tab leaves its
// group, regroups it into a fresh "Claude" group — 9ms after the sweep, measured
// 06-09-2026. Each sweep therefore minted a new saved chip instead of removing one, and
// the bookmarks bar filled with "Claude" chips. So the tabs are CLOSED instead, which
// is what Chrome's own "Delete group" does: with no tab left to regroup, the extension
// drops its record and the group dies with its chip. An abandoned agent session's tabs
// are the whole point of the sweep anyway.
//
// The catch is that an agent's group has to survive while the agent is driving it.
// Ungrouping on sight destroyed the group milliseconds after claude-in-chrome created
// it, so every browser session died on "No group with id" and no agent could use Chrome
// at all. So wait for the group to go quiet instead: a live session touches its tabs
// constantly, an abandoned one never does again.
// Ten minutes. A chip only becomes permanent if Chrome quits while the group is still
// open, and a closed chip is invisible to every extension API, so the window is the
// whole exposure: every group still open when Chrome quits is a chip for ever.
// Thirty minutes lost that race constantly (five leftover chips on one profile,
// 06-09-2026). The cost of closing early is small now that the tabs are closed rather
// than ungrouped: a live session's next browser call simply gets a fresh group.
// ponytail: "touched" means a tab event — navigation, title change, activation. A live
// session that only screenshots and clicks one page for ten minutes fires none and
// gets closed; watch the tab's URL/title on a timer if that ever actually happens.
const IDLE_MS = 10 * 60 * 1000;
const SWEEP_ALARM = 'claude-sweeper-sweep';

// The sweep closes tabs, so a pattern that matches an empty title — "", ".*", "x?" — would
// close every group the user has. Such a pattern, or one that does not compile, matches
// nothing instead. options.js applies the same rule before it saves.
function agentMatcher(source) {
  try {
    const re = new RegExp(source, 'i');
    return re.test('') ? null : re;
  } catch (e) {
    return null;
  }
}

async function readMatcher() {
  const { [PATTERN_KEY]: source = DEFAULT_PATTERN } = await chrome.storage.sync.get(PATTERN_KEY);
  return agentMatcher(source);
}

// ⚠ This map MUST live in storage, not memory. MV3 tears the worker down within seconds
// of it going idle, and the alarm below then starts a fresh one — so an in-memory Map is
// empty at the top of every single sweep. Combined with the rule that an unseen group
// gets a full idle window, that meant every group was marked "seen just now" once a
// minute forever and nothing was ever swept. Silent, because the only symptom is groups
// that quietly stay put. Found 05-09-2026 with six live groups and a sweep that had
// never once fired.
async function readSeen() {
  const { [SEEN_KEY]: seen = {} } = await chrome.storage.local.get(SEEN_KEY);
  return seen;
}

async function writeSeen(seen) {
  await chrome.storage.local.set({ [SEEN_KEY]: seen });
}

chrome.tabGroups.onCreated.addListener(touch);
chrome.tabGroups.onUpdated.addListener(touch);
chrome.tabs.onCreated.addListener(tab => touchGroup(tab.groupId));
chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  try {
    await touchGroup((await chrome.tabs.get(tabId)).groupId);
  } catch (e) {}
});
chrome.tabs.onUpdated.addListener((_id, _change, tab) => touchGroup(tab.groupId));

chrome.runtime.onStartup.addListener(sweep);
chrome.runtime.onInstalled.addListener(ensureAlarm);
chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === SWEEP_ALARM) sweep();
});

// Also at top level: the worker restarts on any event, and an alarm created only on
// install is gone the moment it is cleared or the extension is reloaded by hand.
ensureAlarm();

function ensureAlarm() {
  chrome.alarms.create(SWEEP_ALARM, { periodInMinutes: 1 });
}

async function touch(group) {
  const agent = await readMatcher();
  if (!agent || !agent.test(group.title || '')) return;
  const seen = await readSeen();
  seen[group.id] = Date.now();
  await writeSeen(seen);
}

async function touchGroup(groupId) {
  if (groupId === undefined || groupId === chrome.tabGroups.TAB_GROUP_ID_NONE) return;
  const seen = await readSeen();
  if (!(groupId in seen)) return;
  seen[groupId] = Date.now();
  await writeSeen(seen);
}

async function sweep() {
  ensureAlarm();
  const { [AUTO_KEY]: on = true } = await chrome.storage.sync.get(AUTO_KEY);
  if (!on) return;
  const agent = await readMatcher();
  if (!agent) return;

  let groups;
  try {
    groups = await chrome.tabGroups.query({});
  } catch (e) {
    return;
  }

  const seen = await readSeen();
  const now = Date.now();
  const live = new Set();
  let swept = 0;
  let waiting = 0;

  for (const group of groups) {
    if (!agent.test(group.title || '')) continue;
    live.add(String(group.id));

    // A group this worker has never recorded gets a full idle window rather than being
    // assumed abandoned — but the record survives the worker now, so the window
    // actually elapses.
    if (seen[group.id] === undefined) {
      seen[group.id] = now;
      waiting++;
      continue;
    }
    if (now - seen[group.id] < IDLE_MS) {
      waiting++;
      continue;
    }
    try {
      const tabs = await chrome.tabs.query({ groupId: group.id });
      // One call for all of them: closing the main tab alone makes the extension promote
      // a member and regroup that instead.
      if (tabs.length) await chrome.tabs.remove(tabs.map(t => t.id));
      delete seen[group.id];
      swept++;
    } catch (e) {}
  }

  // Drop records for groups that no longer exist, or the store grows forever.
  for (const id of Object.keys(seen)) {
    if (!live.has(id)) delete seen[id];
  }

  await writeSeen(seen);
  await chrome.storage.local.set({ [STATUS_KEY]: { at: now, swept, waiting } });
}
