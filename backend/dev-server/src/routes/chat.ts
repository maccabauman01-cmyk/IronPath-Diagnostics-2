import type {Request, Response} from "express";
import {z} from "zod";
import {getMachineName} from "../machines.js";
import {
  enrichHitsWithAssets,
  searchMachine,
  searchToContext,
} from "../search.js";
import {runDiagnosticChat, streamDiagnosticChat} from "../../../functions/src/services/openai.js";
import {OPENAI_API_KEY} from "../config.js";

export const contextRecordSchema = z.object({
  id: z.string(),
  title: z.string().optional(),
  body_text: z.string(),
  page_start: z.number().optional(),
  page_end: z.number().optional(),
  smcs: z.array(z.string()).optional(),
  content_type: z.string().optional(),
  has_troubleshooting_table: z.boolean().optional(),
  manual_type: z.string().optional(),
  system: z.string().optional(),
});

export const chatBodySchema = z.object({
  machineId: z.string().min(1),
  message: z.string().min(1).max(4000),
  conversationHistory: z
    .array(
      z.object({
        role: z.enum(["user", "assistant"]),
        content: z.string(),
      }),
    )
    .max(20)
    .default([]),
  searchLimit: z.number().int().min(1).max(15).default(8),
  contextRecords: z.array(contextRecordSchema).min(1).max(15).optional(),
});

type ChatBody = z.infer<typeof chatBodySchema>;

function resolveChatContext(body: ChatBody) {
  const {machineId, message, searchLimit, contextRecords} = body;

  if (contextRecords && contextRecords.length > 0) {
    const hits = contextRecords.map((r) => ({
      recordId: r.id,
      score: 0,
      title: r.title ?? "",
      system: r.system ?? "",
      manual_type: r.manual_type ?? "",
      page_start: r.page_start ?? 0,
      page_end: r.page_end ?? 0,
      content_type: r.content_type ?? "",
      has_troubleshooting_table: r.has_troubleshooting_table ?? false,
      snippet: r.body_text.slice(0, 220),
    }));
    return {context: contextRecords, hits};
  }

  const hits = searchMachine(machineId, message, searchLimit);
  if (hits.length === 0) {
    return null;
  }
  return {context: searchToContext(machineId, hits), hits};
}

function sseWrite(res: Response, event: string, data: unknown) {
  res.write(`event: ${event}\n`);
  res.write(`data: ${JSON.stringify(data)}\n\n`);
}

export async function handleChat(req: Request, res: Response) {
  const parsed = chatBodySchema.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({error: "Invalid body", details: parsed.error.flatten()});
    return;
  }

  if (!OPENAI_API_KEY) {
    res.status(503).json({
      error: "Set OPENAI_API_KEY in backend/.env to run AI chat locally",
    });
    return;
  }

  const {machineId, message, conversationHistory} = parsed.data;
  const resolved = resolveChatContext(parsed.data);

  if (!resolved) {
    res.status(404).json({
      error: "No matching manual records found for this query",
      machineId,
      message,
    });
    return;
  }

  const {context, hits} = resolved;
  const machineName = getMachineName(machineId);

  try {
    const aiResult = await runDiagnosticChat(
      {machineId, machineName, message, conversationHistory, contextRecords: context},
      OPENAI_API_KEY,
    );

    res.json({
      ...aiResult,
      machineId,
      machineName,
      searchResults: enrichHitsWithAssets(machineId, hits),
    });
  } catch (err) {
    console.error("Chat error:", err);
    res.status(502).json({error: "Diagnostic engine failed", detail: String(err)});
  }
}

export async function handleChatStream(req: Request, res: Response) {
  const parsed = chatBodySchema.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({error: "Invalid body", details: parsed.error.flatten()});
    return;
  }

  if (!OPENAI_API_KEY) {
    res.status(503).json({
      error: "Set OPENAI_API_KEY in backend/.env to run AI chat locally",
    });
    return;
  }

  const {machineId, message, conversationHistory} = parsed.data;
  const resolved = resolveChatContext(parsed.data);

  if (!resolved) {
    res.status(404).json({
      error: "No matching manual records found for this query",
      machineId,
      message,
    });
    return;
  }

  const {context, hits} = resolved;
  const machineName = getMachineName(machineId);
  const searchResults = enrichHitsWithAssets(machineId, hits);

  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.flushHeaders?.();

  try {
    for await (const event of streamDiagnosticChat(
      {machineId, machineName, message, conversationHistory, contextRecords: context},
      OPENAI_API_KEY,
    )) {
      if (event.type === "delta") {
        sseWrite(res, "delta", {reply: event.reply});
      } else if (event.type === "checks") {
        sseWrite(res, "checks", {checks: event.checks});
      } else {
        sseWrite(res, "done", {
          ...event.result,
          machineId,
          machineName,
          searchResults,
        });
      }
    }
    res.end();
  } catch (err) {
    console.error("Chat stream error:", err);
    sseWrite(res, "error", {error: "Diagnostic engine failed"});
    res.end();
  }
}
