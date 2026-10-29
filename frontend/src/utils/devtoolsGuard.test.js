import test from 'node:test';
import assert from 'node:assert/strict';
import { isBlockedShortcut } from './devtoolsGuard.js';

const ev = (o) => ({ key: '', code: '', ctrlKey: false, shiftKey: false, altKey: false, metaKey: false, ...o });

test('F12 is blocked', () => assert.equal(isBlockedShortcut(ev({ key: 'F12', code: 'F12' })), true));
test('Ctrl+Shift+I / J / C are blocked', () => {
  for (const k of ['I', 'J', 'C', 'i', 'j']) assert.equal(isBlockedShortcut(ev({ key: k, ctrlKey: true, shiftKey: true })), true, k);
});
test('Ctrl+U (view source) is blocked', () => assert.equal(isBlockedShortcut(ev({ key: 'u', ctrlKey: true })), true));
test('Cmd+Option+I / U are blocked on macOS', () => {
  assert.equal(isBlockedShortcut(ev({ key: 'i', metaKey: true, altKey: true }), true), true);
  assert.equal(isBlockedShortcut(ev({ key: 'u', metaKey: true, altKey: true }), true), true);
});
test('normal typing and common shortcuts still work', () => {
  assert.equal(isBlockedShortcut(ev({ key: 'a' })), false);
  assert.equal(isBlockedShortcut(ev({ key: 'c', ctrlKey: true })), false);   // copy
  assert.equal(isBlockedShortcut(ev({ key: 'v', ctrlKey: true })), false);   // paste
  assert.equal(isBlockedShortcut(ev({ key: 'i', ctrlKey: true })), false);   // Ctrl+I alone
  assert.equal(isBlockedShortcut(ev({ key: 'F5' })), false);
});
