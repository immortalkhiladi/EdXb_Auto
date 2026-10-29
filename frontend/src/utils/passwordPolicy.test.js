import test from 'node:test';
import assert from 'node:assert/strict';
import { passwordProblems, passwordError } from './passwordPolicy.js';

test('accepts valid 4-6 character passwords', () => {
  for (const pw of ['Ab1@', 'A1!x', 'Zz9#yy', 'P4$$wd']) assert.deepEqual(passwordProblems(pw), [], pw);
});

test('rejects invalid lengths with a length message', () => {
  assert.match(passwordError('A1@'), /4 to 6 characters long \(yours has 3\)/);
  assert.match(passwordError('Abcd1@x'), /4 to 6 characters long \(yours has 7\)/);
  assert.match(passwordError(''), /yours has 0/);
});

test('names exactly what is missing', () => {
  assert.match(passwordError('ab1@'), /missing an uppercase letter/);
  assert.match(passwordError('Abc@'), /missing a number/);
  assert.match(passwordError('Abc1'), /missing a special character/);
  assert.match(passwordError('abcd'), /uppercase letter.*number.*special character/);
});

test('letters and digits alone are not special characters; spaces are not either', () => {
  assert.notEqual(passwordError('Ab1 '), '');
  assert.notEqual(passwordError('Ab12'), '');
});

test('too long AND missing a class reports both', () => {
  const p = passwordProblems('abcdefgh');
  assert.equal(p.length, 2);
});
