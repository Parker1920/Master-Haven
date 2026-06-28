import test from 'node:test';
import assert from 'node:assert/strict';
import { isAdminGuild, accessibleGuilds, countAdmin, ADMINISTRATOR } from '../src/framework/guildAccess.js';

test('isAdminGuild: owner counts as admin even with no permission bits', () => {
  assert.equal(isAdminGuild({ id: '1', owner: true, permissions: '0' }), true);
});

test('isAdminGuild: ADMINISTRATOR bit set', () => {
  assert.equal(isAdminGuild({ id: '1', permissions: String(ADMINISTRATOR) }), true);
});

test('isAdminGuild: a typical non-admin permission set is rejected', () => {
  // 104324673 = a common member permission set without ADMINISTRATOR
  assert.equal(isAdminGuild({ id: '1', permissions: '104324673' }), false);
});

test('isAdminGuild: malformed permissions do not throw', () => {
  assert.equal(isAdminGuild({ id: '1', permissions: 'not-a-number' }), false);
  assert.equal(isAdminGuild({}), false);
});

test('accessibleGuilds: returns only (admin ∩ bot-present)', () => {
  const userGuilds = [
    { id: 'A', name: 'Admin + Bot', permissions: String(ADMINISTRATOR) },
    { id: 'B', name: 'Admin, no Bot', permissions: String(ADMINISTRATOR) },
    { id: 'C', name: 'Bot, not Admin', permissions: '0' },
    { id: 'D', name: 'Owner + Bot', owner: true, permissions: '0' },
  ];
  const botGuilds = new Map([
    ['A', 'Admin + Bot'],
    ['C', 'Bot, not Admin'],
    ['D', 'Owner + Bot'],
  ]);
  const ids = accessibleGuilds(userGuilds, botGuilds).map((g) => g.id).sort();
  assert.deepEqual(ids, ['A', 'D']);
});

test('accessibleGuilds: falls back to the bot guild name when the user object lacks one', () => {
  const out = accessibleGuilds([{ id: 'A', permissions: String(ADMINISTRATOR) }], new Map([['A', 'Lily’s server']]));
  assert.equal(out[0].name, 'Lily’s server');
});

test('accessibleGuilds: empty / nullish inputs are safe', () => {
  assert.deepEqual(accessibleGuilds(null, new Map()), []);
  assert.deepEqual(accessibleGuilds([{ id: 'A', owner: true }], new Map()), []);
});

test('countAdmin: counts admin guilds regardless of bot presence', () => {
  const userGuilds = [
    { id: 'A', permissions: String(ADMINISTRATOR) },
    { id: 'B', owner: true },
    { id: 'C', permissions: '0' },
  ];
  assert.equal(countAdmin(userGuilds), 2);
});
