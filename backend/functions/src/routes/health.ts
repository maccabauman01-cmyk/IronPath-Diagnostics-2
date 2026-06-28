import {Router} from "express";

export const healthRouter = Router();

healthRouter.get("/", (_req, res) => {
  res.json({
    status: "ok",
    service: "ironpath-api",
    version: "0.1.0",
  });
});
