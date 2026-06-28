import express, {Express} from "express";
import cors from "cors";
import {healthRouter} from "./routes/health";
import {chatRouter} from "./routes/chat";
import {requireAuth} from "./middleware/auth";

const ALLOWED_ORIGINS = [
  "https://ironpath-diagnostics.web.app",
  "https://ironpath-diagnostics.firebaseapp.com",
  "http://localhost:5173",
  "http://127.0.0.1:5173",
  "http://localhost:4173",
];

export function createApp(): Express {
  const app = express();

  app.use(
    cors({
      origin(origin, callback) {
        if (!origin || ALLOWED_ORIGINS.includes(origin)) {
          callback(null, true);
          return;
        }
        callback(null, false);
      },
      credentials: true,
    }),
  );

  app.use(express.json({limit: "1mb"}));

  app.use("/health", healthRouter);
  app.use("/chat", requireAuth, chatRouter);

  app.use((_req, res) => {
    res.status(404).json({error: "Not found"});
  });

  app.use(
    (
      err: Error,
      _req: express.Request,
      res: express.Response,
      _next: express.NextFunction,
    ) => {
      console.error("Unhandled error:", err);
      res.status(500).json({error: "Internal server error"});
    },
  );

  return app;
}
