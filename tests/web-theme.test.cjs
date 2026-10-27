const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');
const source = readFileSync(new URL('../web/theme.js', `file://${__filename}`), 'utf8');

function browser(saved = null, dark = false, storageAvailable = true) {
  const events = {}, windowEvents = {}, selectorEvents = {};
  const root = { dataset: {}, style: {} };
  const selector = { value: '', addEventListener: (name, fn) => selectorEvents[name] = fn };
  const system = { matches: dark, addEventListener: (name, fn) => events[name] = fn };
  let stored = saved;
  const context = {
    window: { matchMedia: () => system, addEventListener: (name, fn) => windowEvents[name] = fn },
    document: {
      documentElement: root,
      querySelector: () => ({ setAttribute() {} }),
      getElementById: () => selector,
      addEventListener: (name, fn) => events[name] = fn,
    },
    localStorage: {
      getItem() { if (!storageAvailable) throw Error('Unavailable'); return stored; },
      setItem(key, value) { if (!storageAvailable) throw Error('Unavailable'); stored = value; },
    },
  };
  vm.runInNewContext(source, context);
  return {
    root, selector, saved: () => stored,
    ready() { events.DOMContentLoaded(); },
    choose(value) { selector.value = value; selectorEvents.change(); },
    systemDark(value) { system.matches = value; events.change(); },
    otherTab(value) { windowEvents.storage({ key: 'unified-appearance', newValue: value }); },
  };
}

test('first paint follows system and responds to OS changes', () => {
  const b = browser(null, true);
  assert.equal(b.root.dataset.theme, 'dark');
  assert.equal(b.root.dataset.themePreference, 'system');
  b.ready();
  assert.equal(b.selector.value, 'system');
  b.systemDark(false);
  assert.equal(b.root.dataset.theme, 'light');
  assert.equal(b.root.style.colorScheme, 'light');
});
test('all choices persist across reload and explicit choices override the OS', () => {
  const b = browser(); b.ready();
  for (const mode of ['dark', 'light', 'system']) {
    b.choose(mode);
    assert.equal(b.saved(), mode);
    const reloaded = browser(b.saved(), true); reloaded.ready();
    assert.equal(reloaded.selector.value, mode);
    assert.equal(reloaded.root.dataset.theme, mode === 'light' ? 'light' : 'dark');
    reloaded.systemDark(false);
    assert.equal(reloaded.root.dataset.theme, mode === 'dark' ? 'dark' : 'light');
  }
});
test('other tabs and removed preferences apply without reloading', () => {
  const b = browser(); b.ready();
  b.otherTab('dark');
  assert.equal(b.root.dataset.theme, 'dark');
  assert.equal(b.selector.value, 'dark');
  b.otherTab(null);
  assert.equal(b.selector.value, 'system');
  assert.equal(b.root.dataset.theme, 'light');
});
test('invalid or unavailable storage still permits appearance changes', () => {
  assert.equal(browser('invalid').root.dataset.themePreference, 'system');
  const b = browser(null, true, false); b.ready(); b.choose('light');
  assert.equal(b.root.dataset.theme, 'light');
  b.systemDark(true);
  assert.equal(b.root.dataset.theme, 'light');
});
