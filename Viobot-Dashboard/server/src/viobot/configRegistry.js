/**
 * Viobot-specific config registry — mirrors guild_configs.config_json (v1).
 *
 * This is the "modular configuration system": adding a new Viobot option is a single entry here.
 * The generic renderer/validator (Phase 2, framework/configEngine.js) reads this registry and never
 * hard-codes Viobot fields. Defined now (Phase 1) so the schema mirror is locked before write support.
 *
 * field.type → UI control:
 *   role     → single role picker          channel → single channel picker
 *   role[]   → role multi-select           bool    → toggle
 *
 * Confirmed against the live bot source (src/lib/ConfigManager.js `DEFAULTS`) on 2026-06-28.
 * NOTE: the bot caches config in memory (ConfigManager.cache) — a direct DB write won't take
 * effect until the bot reloads that guild, so Phase 2 needs a reload trigger (see INTEGRATION-SPEC §4).
 */
export const CONFIG_VERSION = 1;

export const configRegistry = {
  version: CONFIG_VERSION,
  groups: [
    {
      id: 'roles',
      label: 'Roles',
      fields: [
        { path: 'roles.moderatorRoleId', type: 'role', label: 'Moderator role', help: 'Role allowed to run moderation commands.' },
        { path: 'roles.muteRoleId', type: 'role', label: 'Mute role' },
        { path: 'roles.voiceMuteRoleId', type: 'role', label: 'Voice mute role' },
        { path: 'roles.verificationRequiredRoleId', type: 'role', label: 'Verification-required role' },
        { path: 'roles.staffRoleIds', type: 'role[]', label: 'Staff roles', default: [] },
      ],
    },
    {
      id: 'channels',
      label: 'Channels',
      fields: [
        { path: 'channels.loggingChannelId', type: 'channel', label: 'Logging channel' },
        { path: 'channels.contactMemberChannelId', type: 'channel', label: 'Contact channel (members)' },
        { path: 'channels.contactMutedChannelId', type: 'channel', label: 'Contact channel (muted)' },
        { path: 'channels.papertrailChannelId', type: 'channel', label: 'Papertrail channel' },
        { path: 'channels.violationsChannelId', type: 'channel', label: 'Violations channel' },
      ],
    },
    {
      id: 'features',
      label: 'Features',
      fields: [
        { path: 'features.tickets', type: 'bool', label: 'Tickets', default: false, help: 'Enable the Contact-Us ticket system.' },
        { path: 'features.logger', type: 'bool', label: 'Logger', default: false, help: 'Enable moderation logging.' },
        { path: 'features.autoSusmuteNewAccounts', type: 'bool', label: 'Auto-susmute new accounts', default: false, help: 'Automatically suspicious-mute very new accounts on join.' },
      ],
    },
    // tickets.customContactCategories is a structured array (custom Contact-Us categories), not a
    // simple field — it gets a dedicated editor in Phase 3 alongside aliases/variables.
  ],
};
