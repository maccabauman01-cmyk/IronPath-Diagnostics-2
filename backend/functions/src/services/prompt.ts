import {
  ChatRequest,
  ContextRecord,
  aiResponseSchema,
} from "../types/chat";

const SYSTEM_PROMPT = `You are IronPath, an expert mining equipment diagnostic assistant.

Rules:
- Use ONLY the provided manual excerpts as factual sources. Do not invent procedures, specs, or part numbers.
- Each diagnostic check MUST directly relate to the user's symptom AND the cited excerpt. Do NOT connect unrelated systems (e.g. object detection/radar when the user asks about blade tilt or hydraulics).
- If none of the excerpts match the symptom, say that clearly in the reply and give only generic safe inspection steps — do not cite irrelevant records.
- Rank up to 5 diagnostic checks from most to least likely, based on the user's symptom and the excerpts.
- Each check MUST reference a recordId from the provided context records.
- Use a different recordId for each check when possible.
- Prefer troubleshooting tables, test procedures, and fault-code entries when they match the symptom.
- Check titles and descriptions must reflect what the cited excerpt actually covers.
- Ask 1-3 short follow-up questions when more information would narrow the diagnosis.
- Write for field technicians: clear, actionable, safety-aware.

Respond with valid JSON. **Put "checks" first** so they can stream before the summary reply:
{
  "checks": [
    {
      "rank": 1,
      "title": "short check title",
      "description": "what to do and why",
      "recordId": "id from context",
      "citation": { "page": "p. 12-14", "smcs": "7322", "source": "manual section name" }
    }
  ],
  "reply": "brief summary for the technician",
  "followUpQuestions": ["question 1"],
  "citedRecordIds": ["id1", "id2"]
}`;

function formatRecord(record: ContextRecord, index: number): string {
  const pages =
    record.page_start != null
      ? record.page_end != null && record.page_end !== record.page_start
        ? `p. ${record.page_start}-${record.page_end}`
        : `p. ${record.page_start}`
      : "unknown page";

  const smcs =
    record.smcs && record.smcs.length > 0
      ? record.smcs.join(", ")
      : "n/a";

  return [
    `[Record ${index + 1}]`,
    `id: ${record.id}`,
    `title: ${record.title ?? "(untitled)"}`,
    `type: ${record.content_type ?? "unknown"} | manual: ${record.manual_type ?? "unknown"}`,
    `system: ${record.system ?? "unknown"} | pages: ${pages} | SMCS: ${smcs}`,
    `troubleshooting_table: ${record.has_troubleshooting_table ? "yes" : "no"}`,
    `text:\n${record.body_text.slice(0, 6000)}`,
  ].join("\n");
}

export function buildDiagnosticPrompt(input: ChatRequest): {
  system: string;
  user: string;
} {
  const machineLabel = input.machineName ?? input.machineId;
  const contextBlock = input.contextRecords
    .map((record, i) => formatRecord(record, i))
    .join("\n\n---\n\n");

  const historyBlock =
    input.conversationHistory.length > 0
      ? input.conversationHistory
          .map((m) => `${m.role.toUpperCase()}: ${m.content}`)
          .join("\n")
      : "(no prior messages)";

  const user = [
    `Machine: ${machineLabel} (${input.machineId})`,
    "",
    "Conversation so far:",
    historyBlock,
    "",
    "Latest user message:",
    input.message,
    "",
    "Manual excerpts retrieved locally by the app (authoritative sources):",
    contextBlock,
  ].join("\n");

  return {system: SYSTEM_PROMPT, user};
}

export function parseAiResponse(raw: string) {
  const trimmed = raw.trim();
  const jsonText = trimmed.startsWith("```")
    ? trimmed.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "")
    : trimmed;

  const parsed = JSON.parse(jsonText);
  return aiResponseSchema.parse(parsed);
}

/** Extract partial reply text while JSON is still streaming */
export function extractStreamingReply(accumulated: string): string {
  const key = '"reply"';
  const idx = accumulated.indexOf(key);
  if (idx === -1) return "";

  let i = idx + key.length;
  while (i < accumulated.length && /[\s:]/.test(accumulated[i]!)) i++;
  if (accumulated[i] !== '"') return "";

  i++;
  let result = "";
  while (i < accumulated.length) {
    const c = accumulated[i]!;
    if (c === "\\" && i + 1 < accumulated.length) {
      const next = accumulated[i + 1]!;
      if (next === "n") result += "\n";
      else if (next === "t") result += "\t";
      else if (next === '"') result += '"';
      else if (next === "\\") result += "\\";
      else result += next;
      i += 2;
      continue;
    }
    if (c === '"') break;
    result += c;
    i++;
  }
  return result;
}

/** Extract complete check objects from partial JSON while streaming */
export function extractStreamingChecks(
  accumulated: string,
): Array<{
  rank: number;
  title: string;
  description: string;
  recordId: string;
  citation: {page?: string; smcs?: string; source?: string};
}> {
  const key = '"checks"';
  const idx = accumulated.indexOf(key);
  if (idx === -1) return [];

  let i = idx + key.length;
  while (i < accumulated.length && /[\s:]/.test(accumulated[i]!)) i++;
  if (accumulated[i] !== "[") return [];
  i++;

  const checks: ReturnType<typeof extractStreamingChecks> = [];

  while (i < accumulated.length) {
    while (i < accumulated.length && /[\s,]/.test(accumulated[i]!)) i++;
    if (i >= accumulated.length || accumulated[i] === "]") break;
    if (accumulated[i] !== "{") break;

    let depth = 0;
    const start = i;
    let inString = false;
    let escape = false;

    while (i < accumulated.length) {
      const c = accumulated[i]!;
      if (escape) {
        escape = false;
        i++;
        continue;
      }
      if (c === "\\" && inString) {
        escape = true;
        i++;
        continue;
      }
      if (c === '"') {
        inString = !inString;
        i++;
        continue;
      }
      if (!inString) {
        if (c === "{") depth++;
        else if (c === "}") {
          depth--;
          if (depth === 0) {
            i++;
            try {
              const parsed = JSON.parse(accumulated.slice(start, i));
              if (parsed.title && parsed.recordId) {
                checks.push({
                  rank: parsed.rank ?? checks.length + 1,
                  title: parsed.title,
                  description: parsed.description ?? "",
                  recordId: parsed.recordId,
                  citation: parsed.citation ?? {},
                });
              }
            } catch {
              /* object still malformed */
            }
            break;
          }
        }
      }
      i++;
    }
  }

  return checks;
}
