import { buildApp } from './app.js';
import { env, assertProductionEnv } from './env.js';

assertProductionEnv(); // refuse to boot production with insecure defaults (no-op in dev)

const app = await buildApp();

try {
  await app.listen({ port: env.port, host: env.host });
} catch (err) {
  app.log.error(err);
  process.exit(1);
}
