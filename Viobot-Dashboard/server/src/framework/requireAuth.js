import { env } from '../env.js';
import { getSession } from './session.js';

/** Read + verify the signed session cookie. Returns { sid, session }. */
export function readSession(req) {
  const signed = req.cookies?.[env.session.cookieName];
  if (!signed) return { sid: null, session: null };
  const unsigned = req.unsignCookie(signed);
  if (!unsigned.valid || !unsigned.value) return { sid: null, session: null };
  return { sid: unsigned.value, session: getSession(unsigned.value) };
}

/** Route guard: 401s when there is no authenticated user. Returns the session or null. */
export function requireAuth(req, reply) {
  const { session } = readSession(req);
  if (!session?.user) {
    reply.code(401).send({ error: 'not_authenticated' });
    return null;
  }
  return session;
}
