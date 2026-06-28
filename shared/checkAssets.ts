/** Match diagnostic checks to the most relevant tables and illustrations on a record. */

import {tokenize} from "./search";

export type CheckRef = {
  title: string;
  description: string;
  recordId: string;
};

export type TableRef = {
  table_id: string;
  title?: string;
  type?: string;
  columns: string[];
  rows: string[][];
  rowCount: number;
};

export type IllustrationRef = {
  id: string;
  label: string;
  image_path: string;
  content_hash?: string;
};

function checkText(check: CheckRef): string {
  return `${check.title} ${check.description}`.toLowerCase();
}

function tableHaystack(table: TableRef): string {
  const parts = [
    table.title ?? "",
    table.table_id ?? "",
    table.type ?? "",
    ...(table.columns ?? []),
    ...(table.rows ?? []).flat().slice(0, 12),
  ];
  return parts.join(" ").toLowerCase();
}

function scoreTableForCheck(check: CheckRef, table: TableRef): number {
  const query = checkText(check);
  const tokens = tokenize(query);
  const hay = tableHaystack(table);
  let score = 0;

  for (const token of tokens) {
    if (hay.includes(token)) score += token.length >= 5 ? 4 : 2;
  }

  const title = (table.title ?? table.table_id ?? "").toLowerCase();
  if (title) {
    for (const token of tokens) {
      if (title.includes(token)) score += 8;
    }
  }

  if (table.type === "tools") {
    if (!/\b(tool|multimeter|meter|part number)\b/i.test(query)) score -= 80;
  }

  if (table.type === "test_steps" || table.type === "procedure_steps") score += 6;

  if (/\b(diagnostic code|cat et|electronic technician)\b/i.test(query)) {
    if (/\b(diagnostic code|event code|cat et)\b/i.test(hay)) score += 25;
    if (/\bfuel level|fuel line|fuel tank\b/i.test(hay) && !/\bdiagnostic code\b/i.test(hay)) {
      score -= 40;
    }
  }

  if (/\b(battery|solenoid|starting motor|crank)\b/i.test(query)) {
    if (/\b(battery|solenoid|starting motor|crank|start interlock)\b/i.test(hay)) score += 20;
    if (/\bfuel level|fuel line\b/i.test(hay)) score -= 35;
  }

  if (/\b(voltage|ecm|wiring|electrical connector)\b/i.test(query)) {
    if (/\b(voltage|ecm|connector|wiring|battery)\b/i.test(hay)) score += 20;
  }

  if (/\b(overheat|overheating|temperature|cooling|fan)\b/i.test(query)) {
    if (/\b(overheat|temperature|cooling|fan|oil cooler)\b/i.test(hay)) score += 20;
  }

  return score;
}

export function tablesForCheck(
  check: CheckRef,
  tables: TableRef[],
  max = 2,
): TableRef[] {
  const eligible = tables.filter((t) => t.rowCount > 0 && t.rowCount <= 30);
  if (eligible.length === 0) return [];

  const minScore = 4;
  return eligible
    .map((table) => ({table, score: scoreTableForCheck(check, table)}))
    .filter((x) => x.score >= minScore)
    .sort((a, b) => b.score - a.score)
    .slice(0, max)
    .map((x) => x.table);
}

function illustrationKey(ill: IllustrationRef): string {
  return ill.content_hash?.trim() || ill.image_path?.trim() || ill.id;
}

function scoreIllustrationForCheck(check: CheckRef, ill: IllustrationRef): number {
  const query = checkText(check);
  const tokens = tokenize(query);
  const hay = `${ill.label} ${ill.id} ${ill.image_path}`.toLowerCase();
  let score = 0;

  for (const token of tokens) {
    if (hay.includes(token)) score += 3;
  }

  const idMatch = check.description.match(/\bg\d{8}\b/i);
  if (idMatch && hay.includes(idMatch[0].toLowerCase())) score += 50;

  if (/illustration\s*1/i.test(ill.label) && tokens.length > 0) score += 2;

  if (/_junk|placeholder/i.test(ill.image_path)) score -= 100;

  return score;
}

export function illustrationsForCheck(
  check: CheckRef,
  illustrations: IllustrationRef[] | undefined,
  seen: {recordIds: Set<string>; imagePaths: Set<string>},
  max = 3,
): IllustrationRef[] {
  if (!illustrations?.length) return [];
  if (seen.recordIds.has(check.recordId)) return [];

  seen.recordIds.add(check.recordId);

  const ranked = [...illustrations]
    .map((ill) => ({ill, score: scoreIllustrationForCheck(check, ill)}))
    .sort((a, b) => b.score - a.score);

  const out: IllustrationRef[] = [];
  for (const {ill} of ranked) {
    const key = illustrationKey(ill);
    if (!key || seen.imagePaths.has(key)) continue;
    seen.imagePaths.add(key);
    out.push(ill);
    if (out.length >= max) break;
  }

  return out;
}
