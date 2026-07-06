import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

// Isolate the dashboard store's data dir (validateRegistry/sanitizeAppearance are pure and never
// touch the store file, but keep the import self-contained just in case a fallback load() fires).
process.env.DASHBOARD_DATA_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'vbd-store-'));

const { validateRegistry, sanitizeAppearance } = await import('../src/dashboard/store.js');

// --- validateRegistry ---------------------------------------------------------

test('validateRegistry: a well-formed registry passes', () => {
  const reg = {
    version: 1,
    groups: [
      {
        id: 'roles',
        label: 'Roles',
        fields: [
          { path: 'roles.modRoleId', type: 'role', label: 'Mod role' },
          { path: 'sel.x', type: 'select', label: 'Sel', options: ['a', 'b'] },
        ],
      },
    ],
  };
  assert.equal(validateRegistry(reg), true);
});

test('validateRegistry: groups must be an array', () => {
  assert.throws(() => validateRegistry({}), /groups must be an array/);
  assert.throws(() => validateRegistry(null), /groups must be an array/);
  assert.throws(() => validateRegistry({ groups: {} }), /groups must be an array/);
});

test('validateRegistry: each group needs a non-empty id and label', () => {
  assert.throws(() => validateRegistry({ groups: [{ label: 'L', fields: [] }] }), /needs an id/);
  assert.throws(() => validateRegistry({ groups: [{ id: '  ', label: 'L', fields: [] }] }), /needs an id/);
  assert.throws(() => validateRegistry({ groups: [{ id: 'g', fields: [] }] }), /needs a label/);
});

test('validateRegistry: group fields must be an array', () => {
  assert.throws(() => validateRegistry({ groups: [{ id: 'g', label: 'L' }] }), /fields must be an array/);
});

test('validateRegistry: field path must match the dotted-identifier pattern', () => {
  const bad = (p) => ({ groups: [{ id: 'g', label: 'L', fields: [{ path: p, type: 'bool', label: 'x' }] }] });
  assert.throws(() => validateRegistry(bad('has space')), /invalid field path/);
  assert.throws(() => validateRegistry(bad('has-dash')), /invalid field path/);
  assert.throws(() => validateRegistry(bad('.leading')), /invalid field path/);
  assert.throws(() => validateRegistry(bad('trailing.')), /invalid field path/);
  assert.throws(() => validateRegistry(bad(42)), /invalid field path/);
  // valid ones do not throw
  assert.equal(validateRegistry(bad('a')), true);
  assert.equal(validateRegistry(bad('a.b_c.d1')), true);
});

test('validateRegistry: invalid field type is rejected', () => {
  const reg = { groups: [{ id: 'g', label: 'L', fields: [{ path: 'a.b', type: 'wat', label: 'x' }] }] };
  assert.throws(() => validateRegistry(reg), /invalid type wat/);
});

test('validateRegistry: field needs a non-empty label', () => {
  const reg = { groups: [{ id: 'g', label: 'L', fields: [{ path: 'a.b', type: 'bool' }] }] };
  assert.throws(() => validateRegistry(reg), /needs a label/);
});

test('validateRegistry: select field requires options array', () => {
  const reg = { groups: [{ id: 'g', label: 'L', fields: [{ path: 'a.b', type: 'select', label: 'x' }] }] };
  assert.throws(() => validateRegistry(reg), /needs options/);
});

test('validateRegistry: duplicate field paths across groups are rejected', () => {
  const reg = {
    groups: [
      { id: 'g1', label: 'G1', fields: [{ path: 'a.b', type: 'bool', label: 'x' }] },
      { id: 'g2', label: 'G2', fields: [{ path: 'a.b', type: 'bool', label: 'y' }] },
    ],
  };
  assert.throws(() => validateRegistry(reg), /duplicate field path: a\.b/);
});

// --- sanitizeAppearance -------------------------------------------------------

test('sanitizeAppearance: non-object → empty object', () => {
  assert.deepEqual(sanitizeAppearance(null), {});
  assert.deepEqual(sanitizeAppearance('x'), {});
  assert.deepEqual(sanitizeAppearance(undefined), {});
});

test('sanitizeAppearance: brandName clamped to 60 chars', () => {
  assert.equal(sanitizeAppearance({ brandName: 'x'.repeat(200) }).brandName.length, 60);
});

test('sanitizeAppearance: logo null passes, string clamped, non-string dropped', () => {
  assert.equal(sanitizeAppearance({ logo: null }).logo, null);
  assert.equal(sanitizeAppearance({ logo: 'data:x' }).logo, 'data:x');
  assert.equal('logo' in sanitizeAppearance({ logo: 123 }), false);
});

test('sanitizeAppearance: theme keeps only non-empty string values, clamped to 40', () => {
  const out = sanitizeAppearance({ theme: { primary: '#fff', bad: 5, empty: '', long: 'z'.repeat(80) } });
  assert.equal(out.theme.primary, '#fff');
  assert.equal('bad' in out.theme, false);
  assert.equal('empty' in out.theme, false);
  assert.equal(out.theme.long.length, 40);
});

test('sanitizeAppearance: tabs filtered to objects with string id; label defaults to id; hidden coerced', () => {
  const out = sanitizeAppearance({
    tabs: [
      { id: 'roles', label: 'Roles', hidden: 1 },
      { id: 'ch' }, // label defaults to id
      { label: 'no-id' }, // dropped (no string id)
      null, // dropped
    ],
  });
  assert.equal(out.tabs.length, 2);
  assert.deepEqual(out.tabs[0], { id: 'roles', label: 'Roles', hidden: true });
  assert.deepEqual(out.tabs[1], { id: 'ch', label: 'ch', hidden: false });
});

test('sanitizeAppearance: guidesUrl allows blank, https, and same-origin path; rejects others', () => {
  assert.equal(sanitizeAppearance({ guidesUrl: '' }).guidesUrl, '');
  assert.equal(sanitizeAppearance({ guidesUrl: 'https://x.com/g' }).guidesUrl, 'https://x.com/g');
  assert.equal(sanitizeAppearance({ guidesUrl: '/docs/' }).guidesUrl, '/docs/');
  // rejected shapes are not included at all
  assert.equal('guidesUrl' in sanitizeAppearance({ guidesUrl: 'http://x.com' }), false);
  assert.equal('guidesUrl' in sanitizeAppearance({ guidesUrl: '//evil.com' }), false);
  assert.equal('guidesUrl' in sanitizeAppearance({ guidesUrl: 'javascript:alert(1)' }), false);
});

test('sanitizeAppearance: guidesLabel clamped, guidesEnabled only when boolean', () => {
  assert.equal(sanitizeAppearance({ guidesLabel: 'z'.repeat(60) }).guidesLabel.length, 40);
  assert.equal(sanitizeAppearance({ guidesEnabled: true }).guidesEnabled, true);
  assert.equal('guidesEnabled' in sanitizeAppearance({ guidesEnabled: 'true' }), false);
});
