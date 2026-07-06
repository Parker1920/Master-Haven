import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

// Point the dashboard store at a throwaway temp dir BEFORE importing store.js/configWrite.js,
// so setRegistry() persists there instead of the real data dir. These pure helpers never touch
// the SQLite DB (getDb/getWriteDb), so no better-sqlite3 database is opened by this test.
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'vbd-cfgwrite-'));
process.env.DASHBOARD_DATA_DIR = TMP;

const { env } = await import('../src/env.js');
env.dataDir = TMP; // env was frozen-in at first import elsewhere; force the temp dir either way
const { setRegistry } = await import('../src/dashboard/store.js');
const { applyManaged, sanitizeCategories } = await import('../src/viobot/configWrite.js');

// A registry that exercises every field type applyManaged handles.
const TEST_REGISTRY = {
  version: 1,
  groups: [
    {
      id: 'g',
      label: 'Group',
      fields: [
        { path: 'roles.modRoleId', type: 'role', label: 'Mod role' },
        { path: 'roles.staffRoleIds', type: 'role[]', label: 'Staff roles' },
        { path: 'channels.logChannelId', type: 'channel', label: 'Log channel' },
        { path: 'features.tickets', type: 'bool', label: 'Tickets' },
        { path: 'text.welcome', type: 'string', label: 'Welcome', maxLength: 10 },
        { path: 'text.freeform', type: 'string', label: 'Freeform' },
        { path: 'num.slow', type: 'number', label: 'Slowmode', default: 5 },
        { path: 'num.plain', type: 'number', label: 'Plain number' },
        { path: 'sel.color', type: 'select', label: 'Color', options: ['red', 'green', 'blue'], default: 'red' },
        { path: 'sel.obj', type: 'select', label: 'ObjOptions', options: [{ value: 'a' }, { value: 'b' }], default: 'a' },
        { path: 'admin.secret', type: 'string', label: 'Secret', testing: true },
      ],
    },
  ],
};

setRegistry(TEST_REGISTRY);

const ROLES = [{ id: 'r1' }, { id: 'r2' }, { id: 'r3' }];
const CHANNELS = [{ id: 'c1' }, { id: 'c2' }];

test('applyManaged: role id kept when in guild, nulled when not', () => {
  assert.equal(applyManaged({}, { roles: { modRoleId: 'r1' } }, ROLES, CHANNELS, false).roles.modRoleId, 'r1');
  assert.equal(applyManaged({}, { roles: { modRoleId: 'nope' } }, ROLES, CHANNELS, false).roles.modRoleId, null);
});

test('applyManaged: non-string role id is nulled', () => {
  assert.equal(applyManaged({}, { roles: { modRoleId: 123 } }, ROLES, CHANNELS, false).roles.modRoleId, null);
});

test('applyManaged: channel id kept when in guild, nulled when not', () => {
  assert.equal(applyManaged({}, { channels: { logChannelId: 'c2' } }, ROLES, CHANNELS, false).channels.logChannelId, 'c2');
  assert.equal(applyManaged({}, { channels: { logChannelId: 'c9' } }, ROLES, CHANNELS, false).channels.logChannelId, null);
});

test('applyManaged: bool coercion (truthy/falsy → real booleans)', () => {
  assert.equal(applyManaged({}, { features: { tickets: 1 } }, ROLES, CHANNELS, false).features.tickets, true);
  assert.equal(applyManaged({}, { features: { tickets: 0 } }, ROLES, CHANNELS, false).features.tickets, false);
  assert.equal(applyManaged({}, { features: { tickets: 'yes' } }, ROLES, CHANNELS, false).features.tickets, true);
  assert.equal(applyManaged({}, { features: { tickets: '' } }, ROLES, CHANNELS, false).features.tickets, false);
});

test('applyManaged: role[] filters to in-guild ids and dedupes', () => {
  const out = applyManaged(
    {},
    { roles: { staffRoleIds: ['r1', 'r2', 'r1', 'nope', 'r3', 42] } },
    ROLES,
    CHANNELS,
    false,
  );
  assert.deepEqual(out.roles.staffRoleIds, ['r1', 'r2', 'r3']);
});

test('applyManaged: role[] non-array → empty array', () => {
  const out = applyManaged({}, { roles: { staffRoleIds: 'r1' } }, ROLES, CHANNELS, false);
  assert.deepEqual(out.roles.staffRoleIds, []);
});

test('applyManaged: string clamped to maxLength; null passes through', () => {
  assert.equal(applyManaged({}, { text: { welcome: 'x'.repeat(50) } }, ROLES, CHANNELS, false).text.welcome.length, 10);
  assert.equal(applyManaged({}, { text: { welcome: null } }, ROLES, CHANNELS, false).text.welcome, null);
});

test('applyManaged: string with no maxLength clamps to default 1000', () => {
  const out = applyManaged({}, { text: { freeform: 'y'.repeat(2000) } }, ROLES, CHANNELS, false);
  assert.equal(out.text.freeform.length, 1000);
});

test('applyManaged: number keeps finite value, falls back to field default on non-numeric', () => {
  assert.equal(applyManaged({}, { num: { slow: 30 } }, ROLES, CHANNELS, false).num.slow, 30);
  assert.equal(applyManaged({}, { num: { slow: 'abc' } }, ROLES, CHANNELS, false).num.slow, 5);
  // no default on the field → null
  assert.equal(applyManaged({}, { num: { plain: 'abc' } }, ROLES, CHANNELS, false).num.plain, null);
});

test('applyManaged: select validates against allowed values (string + object options)', () => {
  assert.equal(applyManaged({}, { sel: { color: 'green' } }, ROLES, CHANNELS, false).sel.color, 'green');
  assert.equal(applyManaged({}, { sel: { color: 'magenta' } }, ROLES, CHANNELS, false).sel.color, 'red'); // → default
  assert.equal(applyManaged({}, { sel: { obj: 'b' } }, ROLES, CHANNELS, false).sel.obj, 'b');
  assert.equal(applyManaged({}, { sel: { obj: 'z' } }, ROLES, CHANNELS, false).sel.obj, 'a'); // → default
});

test('applyManaged: testing fields ignored for non-admin writers, applied for admins', () => {
  const asMember = applyManaged({}, { admin: { secret: 'hi' } }, ROLES, CHANNELS, false);
  assert.equal(getPath(asMember, 'admin.secret'), undefined); // not written at all
  const asAdmin = applyManaged({}, { admin: { secret: 'hi' } }, ROLES, CHANNELS, true);
  assert.equal(asAdmin.admin.secret, 'hi');
});

test('applyManaged: unsubmitted fields leave base untouched', () => {
  const base = { roles: { modRoleId: 'r1' }, features: { tickets: true } };
  const out = applyManaged(base, { channels: { logChannelId: 'c1' } }, ROLES, CHANNELS, false);
  assert.equal(out.roles.modRoleId, 'r1'); // untouched
  assert.equal(out.features.tickets, true); // untouched
  assert.equal(out.channels.logChannelId, 'c1'); // applied
});

// --- sanitizeCategories -------------------------------------------------------

test('sanitizeCategories: slugifies id from label, skips reserved ids, dedupes', () => {
  const out = sanitizeCategories(
    [
      { label: 'Billing Help!' }, // → id "billing-help"
      { id: 'report-user', label: 'Report a user' }, // reserved → skipped
      { id: 'other', label: 'Other' }, // reserved → skipped
      { label: 'Billing Help' }, // dupe of billing-help → skipped
    ],
    'actor1',
    [],
  );
  assert.equal(out.length, 1);
  assert.equal(out[0].id, 'billing-help');
  assert.equal(out[0].label, 'Billing Help!');
  assert.equal(out[0].createdBy, 'actor1');
  assert.equal(out[0].isDefault, false);
});

test('sanitizeCategories: caps at 10 entries', () => {
  const many = Array.from({ length: 15 }, (_, i) => ({ label: `Category ${i}` }));
  const out = sanitizeCategories(many, 'actor1', []);
  assert.equal(out.length, 10);
});

test('sanitizeCategories: preserves original createdAt/createdBy from existing entry', () => {
  const existing = [{ id: 'support', label: 'Support', createdAt: '2020-01-01T00:00:00.000Z', createdBy: 'og-user' }];
  const out = sanitizeCategories([{ id: 'support', label: 'Support' }], 'new-actor', existing);
  assert.equal(out.length, 1);
  assert.equal(out[0].createdAt, '2020-01-01T00:00:00.000Z');
  assert.equal(out[0].createdBy, 'og-user');
  assert.equal(out[0].updatedBy, 'new-actor'); // updatedBy is the new actor
});

test('sanitizeCategories: entries missing id AND label are dropped', () => {
  const out = sanitizeCategories([{ label: '' }, { id: '', label: '' }, {}], 'actor1', []);
  assert.deepEqual(out, []);
});

test('sanitizeCategories: strips @everyone/@here and angle brackets from label/description', () => {
  const out = sanitizeCategories([{ label: '@everyone <hi>', description: '@here talk <b>' }], 'actor1', []);
  assert.equal(out[0].label, 'hi');
  assert.equal(out[0].description, 'talk b');
});

test('sanitizeCategories: enabled defaults true, honors explicit false', () => {
  const out = sanitizeCategories([{ label: 'A' }, { label: 'B', enabled: false }], 'actor1', []);
  assert.equal(out.find((c) => c.label === 'A').enabled, true);
  assert.equal(out.find((c) => c.label === 'B').enabled, false);
});

test('sanitizeCategories: non-array input → empty array', () => {
  assert.deepEqual(sanitizeCategories(null, 'actor1', []), []);
  assert.deepEqual(sanitizeCategories(undefined, 'actor1', undefined), []);
});

// local helper mirroring configWrite's getPath, for asserting a path was NOT written
function getPath(o, p) {
  return p.split('.').reduce((x, k) => (x == null ? undefined : x[k]), o);
}
