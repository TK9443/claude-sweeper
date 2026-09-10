// Run: node tests/sweep.test.mjs
//
// The bug this exists to catch: background.js kept its last-seen timestamps in a plain
// Map, MV3 tore the service worker down between alarms, and so every sweep started with
// an empty map, re-marked each group as seen, and swept nothing — forever, silently.
// The test therefore restarts the "worker" between sweeps and only passes if the state
// survives that.

import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
// Overridable so the test can be pointed at an older build to prove it still fails there.
const SOURCE = fs.readFileSync(process.env.CLAUDE_SWEEPER_BG || path.join(ROOT, 'extension', 'background.js'), 'utf8');

const MINUTE = 60 * 1000;

function makeWorld() {
  // Storage is the one thing that outlives a worker restart, which is the whole point.
  const local = {};
  const sync = {};
  let groups = [];
  let tabs = [];
  let now = Date.UTC(2026, 8, 5, 12, 0, 0);
  const ungrouped = [];

  const chrome = {
    storage: {
      local: {
        get: async key => (key in local ? { [key]: local[key] } : {}),
        set: async obj => Object.assign(local, obj),
        onChanged: { addListener() {} }
      },
      sync: {
        get: async key => (key in sync ? { [key]: sync[key] } : {}),
        set: async obj => Object.assign(sync, obj)
      }
    },
    tabGroups: {
      TAB_GROUP_ID_NONE: -1,
      query: async () => groups,
      onCreated: { addListener() {} },
      onUpdated: { addListener() {} }
    },
    tabs: {
      query: async ({ groupId }) => tabs.filter(t => t.groupId === groupId),
      get: async id => tabs.find(t => t.id === id),
      // Closing, not ungrouping: the Claude extension regroups ungrouped tabs instantly.
      remove: async ids => {
        ungrouped.push(...ids);
        tabs = tabs.filter(t => !ids.includes(t.id));
        groups = groups.filter(g => tabs.some(t => t.groupId === g.id));
      },
      onCreated: { addListener() {} },
      onActivated: { addListener() {} },
      onUpdated: { addListener() {} }
    },
    alarms: { create() {}, onAlarm: { addListener() {} } },
    runtime: { onStartup: { addListener() {} }, onInstalled: { addListener() {} } }
  };

  const world = {
    local,
    sync,
    ungrouped,
    setGroups(g, t) {
      groups = g;
      tabs = t;
    },
    groups: () => groups,
    advance(ms) {
      now += ms;
    },
    // Start a fresh service worker: same storage, brand new module scope.
    async runSweep() {
      let alarmCb;
      const ctx = vm.createContext({
        chrome: {
          ...chrome,
          alarms: {
            create() {},
            onAlarm: { addListener: cb => (alarmCb = cb) }
          }
        },
        Date: { ...Date, now: () => now },
        Set,
        Object,
        String,
        console
      });
      vm.runInContext(SOURCE, ctx);
      assert.ok(alarmCb, 'the worker must register an alarm listener');
      alarmCb({ name: 'claude-sweeper-sweep' });
      // The real listener is not async and does not return the sweep's promise, so
      // waiting on it proves nothing; drain the queue instead.
      for (let i = 0; i < 100; i++) await new Promise(r => setImmediate(r));
    }
  };
  return world;
}

const claudeGroup = { id: 1, title: 'Claude' };
const otherGroup = { id: 2, title: 'Research' };
const tabsFor = () => [
  { id: 11, groupId: 1 },
  { id: 12, groupId: 1 },
  { id: 21, groupId: 2 }
];

async function main() {
  const w = makeWorld();
  w.setGroups([claudeGroup, otherGroup], tabsFor());

  // First sweep: the group has never been recorded, so it gets a full idle window.
  await w.runSweep();
  assert.deepStrictEqual(w.ungrouped, [], 'must not sweep a group on first sight');
  assert.ok(w.local.lastSeen && '1' in w.local.lastSeen,
    'the first sweep must persist a timestamp that outlives the worker');

  // Worker restarts every minute; the group is still inside its window.
  w.advance(5 * MINUTE);
  await w.runSweep();
  assert.deepStrictEqual(w.ungrouped, [], 'must not sweep inside the idle window');

  // Past ten minutes with nothing touching it.
  w.advance(6 * MINUTE);
  await w.runSweep();
  assert.deepStrictEqual(w.ungrouped.sort(), [11, 12],
    'must close the tabs of a Claude group idle beyond the window');
  assert.ok(w.groups().every(g => g.id !== 1), 'the emptied group must be gone');
  assert.ok(w.groups().some(g => g.id === 2), 'a non-Claude group must be left alone');
  assert.strictEqual(w.local.lastSweep.swept, 1, 'the sweep must be reported for the UI');

  // Records for groups that no longer exist must not accumulate.
  assert.ok(!('1' in w.local.lastSeen), 'a swept group must be dropped from the store');

  // The sweep closes tabs, so a pattern that matches every title must match none.
  for (const pattern of ['', '.*']) {
    const v = makeWorld();
    v.sync.titlePattern = pattern;
    v.setGroups([claudeGroup, otherGroup], tabsFor());
    await v.runSweep();
    v.advance(11 * MINUTE);
    await v.runSweep();
    assert.deepStrictEqual(v.ungrouped, [], `pattern ${JSON.stringify(pattern)} must close nothing`);
  }

  // A custom pattern targets another agent's groups and leaves Claude's alone.
  const c = makeWorld();
  c.sync.titlePattern = 'research';
  c.setGroups([claudeGroup, otherGroup], tabsFor());
  await c.runSweep();
  c.advance(11 * MINUTE);
  await c.runSweep();
  assert.deepStrictEqual(c.ungrouped, [21], 'a custom pattern must sweep only the groups it names');

  console.log('ok — sweeps only after the idle window, survives worker restarts, and honours the title pattern');
}

main().catch(e => {
  console.error(e.message);
  process.exit(1);
});
