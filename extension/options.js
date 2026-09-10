const AUTO_KEY = 'autoUngroup';
const STATUS_KEY = 'lastSweep';
const PATTERN_KEY = 'titlePattern';
const DEFAULT_PATTERN = 'claude';
const HELP = 'Case-insensitive regular expression';

const auto = document.getElementById('auto');
const pattern = document.getElementById('pattern');
const help = document.getElementById('pattern-help');

// The rule background.js applies: the sweep closes tabs, so a pattern that matches an empty
// title would close every group. Such a pattern is never saved.
function problem(source) {
  try {
    return new RegExp(source, 'i').test('') ? 'Matches every group, so it is not saved' : '';
  } catch (e) {
    return 'Not a valid regular expression, so it is not saved';
  }
}

chrome.storage.sync.get([AUTO_KEY, PATTERN_KEY]).then(result => {
  auto.checked = result[AUTO_KEY] ?? true;
  pattern.value = result[PATTERN_KEY] ?? DEFAULT_PATTERN;
});

auto.addEventListener('change', () => chrome.storage.sync.set({ [AUTO_KEY]: auto.checked }));

pattern.addEventListener('input', () => {
  const message = problem(pattern.value);
  pattern.setAttribute('aria-invalid', message ? 'true' : 'false');
  help.textContent = message || HELP;
  help.classList.toggle('bad', Boolean(message));
});

// On change, not on every keystroke: storage.sync allows only so many writes a minute.
pattern.addEventListener('change', () => {
  if (!problem(pattern.value)) chrome.storage.sync.set({ [PATTERN_KEY]: pattern.value });
});

// The sweep is silent by design, so this is the only sign that it is alive.
async function showStatus() {
  const { [STATUS_KEY]: last } = await chrome.storage.local.get(STATUS_KEY);
  if (!last) return;
  document.getElementById('at').textContent = new Date(last.at).toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit'
  });
  document.getElementById('waiting').textContent = last.waiting;
  document.getElementById('swept').textContent = last.swept;
}

showStatus();
chrome.storage.local.onChanged.addListener(changes => {
  if (changes[STATUS_KEY]) showStatus();
});
