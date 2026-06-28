// Container-behavior integration via Fastify inject. Run with the prod-ish env:
//   DEV_LOGIN=1 WEB_DIST=<abs web/dist> VIOBOT_DB_PATH=./dev-fixtures/pi_viobot.db node test/integration.mjs
// Verifies: SPA is served, dev-login works, and a dev session lists bot-present guilds. (Not a *.test
// file, so `npm test` won't run it under default env where these assertions wouldn't apply.)
import { buildApp } from '../src/app.js';

const app = await buildApp({ logger: false });
let fail = 0;
const ok = (n, c, d) => { console.log(`${c ? 'PASS' : 'FAIL'}  ${n}${d ? '  — ' + d : ''}`); if (!c) fail++; };

const h = (await app.inject({ method: 'GET', url: '/api/health' })).json();
ok('health.devLogin true', h.devLogin === true);
ok('health.serveStatic true', h.serveStatic === true, `WEB_DIST=${process.env.WEB_DIST}`);
ok('db opened query_only (no-write guard)', h.db?.queryOnly === true, `journal=${h.db?.journalMode}`);

const idx = await app.inject({ method: 'GET', url: '/' });
ok('GET / serves the SPA html', idx.statusCode === 200 && /<div id="root">/.test(idx.body));

const dl = await app.inject({ method: 'GET', url: '/api/auth/dev-login' });
const sc = [].concat(dl.headers['set-cookie'] || []);
ok('dev-login → 302 + session cookie', dl.statusCode === 302 && sc.join(';').includes('vbd_sid='));
const cookie = (sc[0] || '').split(';')[0];

const g = await app.inject({ method: 'GET', url: '/api/guilds', headers: { cookie } });
const gj = g.json();
ok('dev session lists bot-present guilds', g.statusCode === 200 && gj.dev === true && Array.isArray(gj.guilds),
  `${gj.guilds?.length} guilds, botPresent ${gj.counts?.botPresent}`);

await app.close();
console.log(fail === 0 ? '\nINTEGRATION OK' : `\nINTEGRATION FAILED (${fail})`);
process.exit(fail ? 1 : 0);
