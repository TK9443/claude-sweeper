// Deletes saved agent tab groups — the chips Chrome keeps in the bookmarks bar after a
// group is closed — straight out of each profile's sync store. The extension can only act on
// a group while it is still open; a closed chip is invisible to every extension API, and
// the only copy of it is here:
//   <profile>\Sync Data\LevelDB   keys  saved_tab_group-dt-<guid>  (SavedTabGroupData wrapping the specifics)
//                                        saved_tab_group-md-<guid>  (sync EntityMetadata)
// A group and each of its tabs are separate entities; a tab points at its group by
// group_guid. Both dt and md rows go, for the group and every tab in it.
//
// Chrome must be closed: LevelDB holds an exclusive LOCK and a half-written store is a
// corrupt profile. The folder is copied to the backups folder before anything is deleted,
// and copies older than fourteen days are removed at the start of each deleting run.
//
// Usage:  node purge.mjs            dry run — lists what would go
//         node purge.mjs --delete   does it
//         --match <regex>           group title to match (default: claude, case-insensitive)
//         --profile <dir>           one profile folder instead of every one under User Data
//         --log <file>              also append every line, timestamped, to this file (for
//                                   the logon task, whose window nobody sees)

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execSync } from 'node:child_process';
import { ClassicLevel } from 'classic-level';

const args = process.argv.slice(2);
const flag = (name) => { const i = args.indexOf(name); return i === -1 ? undefined : args[i + 1]; };
const DELETE = args.includes('--delete');
const MATCH = new RegExp(flag('--match') ?? 'claude', 'i');
if (MATCH.test('')) {
  console.error(`--match /${MATCH.source}/ matches an empty title, so it would delete every saved group. Refusing.`);
  process.exit(2);
}
const PREFIX = 'saved_tab_group';
const LOG = flag('--log');
if (LOG) {
  fs.mkdirSync(path.dirname(LOG), { recursive: true });
  const stamp = () => { const d = new Date(); const p = (n) => String(n).padStart(2, '0'); return `${p(d.getDate())}-${p(d.getMonth() + 1)}-${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`; };
  for (const m of ['log', 'error']) { const orig = console[m].bind(console); console[m] = (...a) => { orig(...a); fs.appendFileSync(LOG, `${stamp()} ${a.join(' ')}
`); }; }
}
const userData = process.platform === 'win32'
  ? path.join(process.env.LOCALAPPDATA, 'Google', 'Chrome', 'User Data')
  : path.join(os.homedir(), 'Library', 'Application Support', 'Google', 'Chrome');
const BACKUPS = process.platform === 'win32'
  ? path.join(process.env.LOCALAPPDATA, 'Claude Sweeper', 'backups')
  : path.join(os.homedir(), 'Library', 'Application Support', 'Claude Sweeper', 'backups');
const KEEP_MS = 14 * 24 * 60 * 60 * 1000;

function pruneBackups() {
  if (!fs.existsSync(BACKUPS)) return;
  for (const name of fs.readdirSync(BACKUPS)) {
    const dir = path.join(BACKUPS, name);
    if (Date.now() - fs.statSync(dir).mtimeMs > KEEP_MS) fs.rmSync(dir, { recursive: true, force: true });
  }
}

function chromeRunning() {
  try {
    // tasklist prints the image name; pgrep prints only PIDs, so test for any output there.
    if (process.platform === 'win32') return /chrome[.]exe/i.test(execSync('tasklist /FI "IMAGENAME eq chrome.exe" /NH', { encoding: 'utf8' }));
    return execSync('pgrep -x "Google Chrome" || true', { encoding: 'utf8' }).trim().length > 0;
  } catch { return false; }
}

// Minimal protobuf wire-format reader: enough for SavedTabGroupSpecifics, which only uses
// varints and length-delimited fields.
function fields(buf) {
  const out = [];
  let i = 0;
  const varint = () => { let n = 0n, s = 0n; for (;;) { const b = buf[i++]; n |= BigInt(b & 0x7f) << s; if (!(b & 0x80)) return n; s += 7n; } };
  while (i < buf.length) {
    const tag = Number(varint());
    const num = tag >> 3, wt = tag & 7;
    if (wt === 0) out.push([num, varint()]);
    else if (wt === 2) { const len = Number(varint()); out.push([num, buf.subarray(i, i + len)]); i += len; }
    else if (wt === 1) { i += 8; }
    else if (wt === 5) { i += 4; }
    else throw new Error(`unsupported wire type ${wt}`);
  }
  return out;
}
const field = (fs, n) => fs.find(([k]) => k === n)?.[1];
// A field number can carry a varint in one entity and bytes in another; only bytes are text.
const str = (v) => (Buffer.isBuffer(v) ? v.toString('utf8') : '');

function parseSpecifics(buf) {
  // The row is SavedTabGroupData: field 1 a version int, field 2 the SavedTabGroupSpecifics.
  const outer = fields(buf);
  const inner = field(outer, 2);
  if (!Buffer.isBuffer(inner)) return { guid: '', kind: 'unknown' };
  const top = fields(inner);
  const guid = str(field(top, 1));
  const group = field(top, 4);
  const tab = field(top, 5);
  if (Buffer.isBuffer(group)) return { guid, kind: 'group', title: str(field(fields(group), 2)) };
  if (Buffer.isBuffer(tab)) { const t = fields(tab); return { guid, kind: 'tab', groupGuid: str(field(t, 1)), title: str(field(t, 4)) }; }
  return { guid, kind: 'unknown' };
}

async function purgeProfile(profileDir) {
  const store = path.join(profileDir, 'Sync Data', 'LevelDB');
  if (!fs.existsSync(path.join(store, 'CURRENT'))) return null;
  // Before opening: once open, this process holds the LOCK and the copy fails on it.
  let backup;
  if (DELETE) {
    const d = new Date();
    const stamp = `${String(d.getDate()).padStart(2, '0')}-${String(d.getMonth() + 1).padStart(2, '0')}-${d.getFullYear()}-${String(d.getHours()).padStart(2, '0')}${String(d.getMinutes()).padStart(2, '0')}${String(d.getSeconds()).padStart(2, '0')}`;
    backup = path.join(BACKUPS, `${path.basename(profileDir)}-${stamp}`);
    fs.cpSync(store, backup, { recursive: true, filter: (p) => path.basename(p) !== 'LOCK' });
  }
  const db = new ClassicLevel(store, { keyEncoding: 'buffer', valueEncoding: 'buffer', createIfMissing: false });
  await db.open();
  try { return await purgeOpen(db, profileDir, backup); } finally { await db.close(); }
}

async function purgeOpen(db, profileDir, backup) {
  const groups = new Map();
  const tabs = [];
  for await (const [k, v] of db.iterator({ gte: Buffer.from(`${PREFIX}-dt-`), lt: Buffer.from(`${PREFIX}-dt.`) })) {
    const e = parseSpecifics(v);
    if (e.kind === 'group') groups.set(e.guid, { ...e, tabs: 0 });
    else if (e.kind === 'tab') tabs.push(e);
  }
  for (const t of tabs) { const g = groups.get(t.groupGuid); if (g) g.tabs++; }
  const doomed = [...groups.values()].filter((g) => MATCH.test(g.title));
  const doomedGuids = new Set(doomed.map((g) => g.guid));
  const keys = [];
  for (const g of doomed) keys.push(g.guid);
  for (const t of tabs) if (doomedGuids.has(t.groupGuid)) keys.push(t.guid);

  const name = path.basename(profileDir);
  console.log(`${name}: ${groups.size} saved group(s), ${doomed.length} matching /${MATCH.source}/i`);
  for (const g of doomed) console.log(`  ${JSON.stringify(g.title)}  ${g.tabs} tab(s)`);

  if (DELETE && keys.length) {
    const batch = db.batch();
    for (const guid of keys) { batch.del(Buffer.from(`${PREFIX}-dt-${guid}`)); batch.del(Buffer.from(`${PREFIX}-md-${guid}`)); }
    await batch.write();
    console.log(`  deleted ${keys.length} entities (${doomed.length} groups + tabs); backup at ${backup}`);
  }
  return { groups: groups.size, doomed: doomed.length };
}

const one = flag('--profile');
const profiles = one ? [path.resolve(one)] : fs.readdirSync(userData).map((d) => path.join(userData, d));
// A copy of a profile somewhere else is not locked by Chrome; only the live ones are.
if (profiles.some((p) => p.startsWith(userData)) && chromeRunning()) {
  console.error('Chrome is running. Quit it fully (check the tray) and run again.');
  process.exit(2);
}
if (DELETE) pruneBackups();
// The app rebuilds its table from the last run in the log, so each run says where it starts.
console.log(`run ${DELETE ? 'delete' : 'count'} /${MATCH.source}/i`);
let any = false;
for (const p of profiles) {
  try { if (await purgeProfile(p)) any = true; }
  catch (e) { console.error(`${path.basename(p)}: ${e.message}`); }
}
if (!any) console.log('No profile with a sync store found.');
if (!DELETE) console.log('Dry run. Add --delete to remove them.');
