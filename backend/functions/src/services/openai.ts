import OpenAI from "openai";
import {ChatRequest, ChatResponse} from "../types/chat";
import {
  buildDiagnosticPrompt,
  extractStreamingChecks,
  extractStreamingReply,
  parseAiResponse,
} from "./prompt";

/** Production default — override with OPENAI_MODEL env (e.g. gpt-4o-mini for dev) */
export const PRODUCTION_MODEL = "gpt-4o";

export function resolveOpenAiModel(override?: string): string {
  return override ?? process.env.OPENAI_MODEL ?? PRODUCTION_MODEL;
}

export async function runDiagnosticChat(
  input: ChatRequest,
  apiKey: string,
  options?: {model?: string},
): Promise<ChatResponse> {
  const model = resolveOpenAiModel(options?.model);
  const client = new OpenAI({apiKey});
  const {system, user} = buildDiagnosticPrompt(input);

  const completion = await client.chat.completions.create({
    model,
    temperature: 0.2,
    response_format: {type: "json_object"},
    messages: [
      {role: "system", content: system},
      {role: "user", content: user},
    ],
  });

  const content = completion.choices[0]?.message?.content;
  if (!content) {
    throw new Error("OpenAI returned an empty response");
  }

  return parseAiResponse(content);
}

export type StreamChatEvent =
  | {type: "delta"; reply: string}
  | {type: "checks"; checks: ChatResponse["checks"]}
  | {type: "done"; result: ChatResponse};

/** Stream diagnostic reply text, then return parsed structured result */
export async function* streamDiagnosticChat(
  input: ChatRequest,
  apiKey: string,
  options?: {model?: string},
): AsyncGenerator<StreamChatEvent> {
  const model = resolveOpenAiModel(options?.model);
  const client = new OpenAI({apiKey});
  const {system, user} = buildDiagnosticPrompt(input);

  const stream = await client.chat.completions.create({
    model,
    temperature: 0.2,
    stream: true,
    response_format: {type: "json_object"},
    messages: [
      {role: "system", content: system},
      {role: "user", content: user},
    ],
  });

  let accumulated = "";
  let lastReply = "";
  let lastCheckCount = 0;

  for await (const chunk of stream) {
    const delta = chunk.choices[0]?.delta?.content ?? "";
    if (!delta) continue;

    accumulated += delta;
    const reply = extractStreamingReply(accumulated);
    if (reply && reply !== lastReply) {
      lastReply = reply;
      yield {type: "delta", reply};
    }

    const checks = extractStreamingChecks(accumulated);
    if (checks.length > lastCheckCount) {
      lastCheckCount = checks.length;
      yield {type: "checks", checks};
    }
  }

  if (!accumulated.trim()) {
    throw new Error("OpenAI returned an empty response");
  }

  yield {type: "done", result: parseAiResponse(accumulated)};
}
