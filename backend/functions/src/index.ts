import {setGlobalOptions} from "firebase-functions/v2";
import {onRequest} from "firebase-functions/v2/https";
import {createApp} from "./app";

setGlobalOptions({
  region: "us-central1",
  maxInstances: 10,
});

const app = createApp();

/**
 * HTTPS API — Auth + diagnostic chat only.
 * Manual data lives in WatermelonDB on the client; this function never stores manuals.
 *
 * OpenAI key: set in functions/.env.ironpath-diagnostics (see npm run sync-env)
 *
 * Routes:
 *   GET  /health
 *   POST /chat          (requires Firebase Auth Bearer token)
 *   POST /chat/stream   (SSE — requires Firebase Auth Bearer token)
 */
export const api = onRequest(
  {
    cors: true,
    timeoutSeconds: 120,
    memory: "512MiB",
  },
  app,
);
