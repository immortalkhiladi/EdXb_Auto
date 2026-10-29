import test from 'node:test';
import assert from 'node:assert/strict';
import { canAccessPage } from './rbac.js';

test('USER: own pages only', () => {
  assert.equal(canAccessPage('USER', 'documents'), true);
  assert.equal(canAccessPage('USER', 'allDocuments'), false);
  assert.equal(canAccessPage('USER', 'admin'), false);
});
test('MD: all documents but no admin console', () => {
  assert.equal(canAccessPage('MD', 'allDocuments'), true);
  assert.equal(canAccessPage('md', 'documents'), true);
  assert.equal(canAccessPage('MD', 'admin'), false);
});
test('ADMIN: everything', () => {
  for (const p of ['documents', 'allDocuments', 'admin', 'settings']) assert.equal(canAccessPage('ADMIN', p), true);
});
test('unknown / missing role: nothing', () => {
  assert.equal(canAccessPage(undefined, 'dashboard'), false);
  assert.equal(canAccessPage('GUEST', 'dashboard'), false);
});

test('USER sees only the tools the admin assigned (example: user01 has the first two)', () => {
  const tools = ['redline-to-gofiler-html', 'html-converter'];
  assert.equal(canAccessPage('USER', 'redline', tools), true);
  assert.equal(canAccessPage('USER', 'gofilerhtml', tools), true);
  assert.equal(canAccessPage('USER', 'secforms', tools), false);
  assert.equal(canAccessPage('USER', 'converter', tools), false);
  assert.equal(canAccessPage('USER', 'documents', tools), true); // non-tool pages are unaffected
  assert.equal(canAccessPage('USER', 'converter', undefined), false);
  assert.equal(canAccessPage('USER', 'converter', []), false);
});
test('ADMIN and MD keep all four tools regardless of the list', () => {
  for (const role of ['ADMIN', 'MD']) for (const p of ['redline', 'gofilerhtml', 'converter', 'secforms']) assert.equal(canAccessPage(role, p, []), true);
});
