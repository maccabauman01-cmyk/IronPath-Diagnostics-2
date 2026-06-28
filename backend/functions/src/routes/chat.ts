import {Router, Response} from "express";
import {chatRequestSchema} from "../types/chat";
import {runDiagnosticChat, streamDiagnosticChat} from "../services/openai";
import {AuthedRequest} from "../middleware/auth";
import {getOpenAiKey} from "../config";

export const chatRouter = Router();

function sseWrite(res: Response, event: string, data: unknown) {
  res.write(`event: ${event}\n`);
  res.write(`data: ${JSON.stringify(data)}\n\n`);
}

chatRouter.post("/", async (req: AuthedRequest, res) => {
  const parsed = chatRequestSchema.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({
      error: "Invalid request body",
      details: parsed.error.flatten(),
    });
    return;
  }

  const apiKey = getOpenAiKey();
  if (!apiKey) {
    res.status(503).json({error: "OpenAI is not configured on the server"});
    return;
  }

  try {
    const result = await runDiagnosticChat(parsed.data, apiKey);
    res.json({
      ...result,
      machineId: parsed.data.machineId,
      machineName: parsed.data.machineName ?? parsed.data.machineId,
    });
  } catch (err) {
    console.error("Chat error:", err);
    res.status(502).json({error: "Diagnostic engine failed to respond"});
  }
});

/** SSE stream — reply + checks incrementally, then done */
chatRouter.post("/stream", async (req: AuthedRequest, res) => {
  const parsed = chatRequestSchema.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({
      error: "Invalid request body",
      details: parsed.error.flatten(),
    });
    return;
  }

  const apiKey = getOpenAiKey();
  if (!apiKey) {
    res.status(503).json({error: "OpenAI is not configured on the server"});
    return;
  }

  const {machineId, machineName} = parsed.data;

  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.flushHeaders?.();

  try {
    for await (const event of streamDiagnosticChat(parsed.data, apiKey)) {
      if (event.type === "delta") {
        sseWrite(res, "delta", {reply: event.reply});
      } else if (event.type === "checks") {
        sseWrite(res, "checks", {checks: event.checks});
      } else {
        sseWrite(res, "done", {
          ...event.result,
          machineId,
          machineName: machineName ?? machineId,
        });
      }
    }
    res.end();
  } catch (err) {
    console.error("Chat stream error:", err);
    sseWrite(res, "error", {error: "Diagnostic engine failed to respond"});
    res.end();
  }
});
