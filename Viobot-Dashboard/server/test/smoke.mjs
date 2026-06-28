// End-to-end smoke via Fastify inject (no network, no sleeps).
// Verifies: health + DB read against the fixture, and that protected routes guard correctly.
import { buildApp } from '../src/app.js';

const app = await buildApp({ logger: false });
let failures = 0;
const check = (name, cond, detail) => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + detail : ''}`);
  if (!cond) failures++;
};

const health = await app.inject({ method: 'GET', url: '/api/health' });
const h = health.json();
check('GET /api/health → 200', health.statusCode === 200);
check('health reads Viobot DB (read-only)', h.db && !h.db.error, JSON.stringify(h.db));
check('health reports registeredGuilds', typeof h.db?.registeredGuilds === 'number', `${h.db?.registeredGuilds} guilds`);

const me = await app.inject({ method: 'GET', url: '/api/auth/me' });
check('GET /api/auth/me without session → 401', me.statusCode === 401);

const guilds = await app.inject({ method: 'GET', url: '/api/guilds' });
check('GET /api/guilds without session → 401', guilds.statusCode === 401);

const login = await app.inject({ method: 'GET', url: '/api/auth/login' });
check('GET /api/auth/login without OAuth creds → 503', login.statusCode === 503, login.json()?.error);

await app.close();
console.log(failures === 0 ? '\nSMOKE OK' : `\nSMOKE FAILED (${failures})`);
process.exit(failures === 0 ? 0 : 1);
