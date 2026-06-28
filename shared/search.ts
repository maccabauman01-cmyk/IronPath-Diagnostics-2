/** Shared local manual search scoring (web, mobile, backend). */

export type SearchableRecord = {
  id?: string;
  title: string;
  body_text: string;
  system?: string;
  manual_type?: string;
  content_type?: string;
  smcs?: string[];
  has_troubleshooting_table?: boolean;
  fault_codes?: unknown[];
};

const STOPWORDS = new Set([
  "the", "and", "for", "not", "with", "has", "have", "this", "that", "from",
  "are", "was", "were", "will", "can", "what", "when", "where", "how", "why",
  "machine", "issue", "problem", "fault", "code", "does", "dont", "can't", "won",
]);

const IMPLEMENT_TERMS =
  /\b(blade|ripper|tilt|implement|dozer|bulldozer|bucket|boom|stick|lift|cylinder|solenoid|hydraulic)\b/i;

const IRRELEVANT_TOPICS = [
  "object detection",
  "cat detect",
  "radar angle",
  "medium range radar",
  "short range radar",
  "off-highway truck",
  "camera view",
  "display module",
  "configuration screen",
  "refrigerant",
  "accumulator",
  "air conditioning",
];

const PHRASE_BOOSTS: Array<{pattern: RegExp; points: number}> = [
  {pattern: /\bblade tilt left\b/i, points: 80},
  {pattern: /\bblade tilt right\b/i, points: 80},
  {pattern: /\btilt left\b/i, points: 50},
  {pattern: /\btilt right\b/i, points: 50},
  {pattern: /\bblade tilt\b/i, points: 45},
  {pattern: /\btilt cylinder\b/i, points: 40},
  {pattern: /\btilt solenoid\b/i, points: 40},
  {pattern: /\bimplement control\b/i, points: 30},
  {pattern: /\bhydraulic pressure\b/i, points: 25},
  {pattern: /\bengine overheat/i, points: 40},
  {pattern: /\btransmission slip/i, points: 40},
  {pattern: /\b(not starting|won't start|wont start|doesn't start|doesnt start|not start)\b/i, points: 35},
  {pattern: /\b(not cranking|won't crank|wont crank|doesn't crank|doesnt crank|not crank)\b/i, points: 40},
  {pattern: /\b(cranks but|turns over but)\b/i, points: 40},
  {pattern: /\bhydraulic oil overheat/i, points: 45},
];

const RECORD_TOPIC_BOOSTS: Array<{query: RegExp; record: RegExp; points: number}> = [
  {query: /\b(not cranking|won't crank|doesn't crank|not crank)\b/i, record: /does not crank/i, points: 70},
  {query: /\b(not starting|won't start|doesn't start|not start)\b/i, record: /starting circuit|does not crank/i, points: 45},
  {query: /\b(not starting|won't start|doesn't start|not start)\b/i, record: /cranks but does not start/i, points: 15},
  {query: /\b(cranks but|turns over but)\b/i, record: /cranks but does not start/i, points: 70},
  {query: /\b(cranks but|turns over but)\b/i, record: /does not crank/i, points: -30},
  {query: /\b(diagnostic code|cat et)\b/i, record: /diagnostic codes|event codes/i, points: 40},
  {query: /\b(overheat|overheating)\b/i, record: /overheat|temperature|cooling|oil cooler/i, points: 35},
];

export function tokenize(query: string): string[] {
  return query
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, " ")
    .split(/\s+/)
    .filter((w) => w.length > 2 && !STOPWORDS.has(w));
}

function countToken(hay: string, token: string): number {
  let count = 0;
  let idx = 0;
  while ((idx = hay.indexOf(token, idx)) !== -1) {
    count++;
    idx += token.length;
  }
  return count;
}

function queryWantsImplement(query: string): boolean {
  return IMPLEMENT_TERMS.test(query);
}

function recordText(record: SearchableRecord): string {
  return [
    record.title,
    record.body_text,
    record.system ?? "",
    record.manual_type ?? "",
    record.content_type ?? "",
    (record.smcs ?? []).join(" "),
    ...(record.fault_codes ?? []).map((fc) => JSON.stringify(fc)),
  ]
    .join(" ")
    .toLowerCase();
}

export function scoreRecord(record: SearchableRecord, query: string, tokens: string[]): number {
  if (tokens.length === 0) return 0;

  const hay = recordText(record);
  const titleHay = (record.title ?? "").toLowerCase();
  const leadHay = (record.body_text ?? "").slice(0, 800).toLowerCase();
  const wantsImplement = queryWantsImplement(query);

  let score = 0;

  for (const token of tokens) {
    const titleHits = countToken(titleHay, token);
    const leadHits = countToken(leadHay, token);
    const bodyHits = countToken(hay, token) - titleHits;

    if (titleHits > 0) score += titleHits * (token.length >= 5 ? 12 : 8);
    if (leadHits > 0) score += leadHits * (token.length >= 5 ? 6 : 4);
    if (bodyHits > 0) score += bodyHits * (token.length >= 5 ? 3 : 2);
  }

  for (const {pattern, points} of PHRASE_BOOSTS) {
    if (pattern.test(query) && (pattern.test(record.title) || pattern.test(record.body_text))) {
      score += points;
    }
  }

  for (const {query: q, record: rec, points} of RECORD_TOPIC_BOOSTS) {
    if (q.test(query) && (rec.test(record.title) || rec.test(record.body_text))) {
      score += points;
    }
  }

  if (/\bstarting circuit\b/i.test(record.title)) score += 10;
  if (/\bdiagnostic codes\b/i.test(record.title)) score += 8;

  if (record.has_troubleshooting_table) score += 20;
  if (record.content_type?.includes("troubleshooting")) score += 15;
  if (record.manual_type === "troubleshooting") score += 12;
  if (record.manual_type === "testing-and-adjusting") score += 8;
  if (record.fault_codes && record.fault_codes.length > 0) score += 10;

  if (/^illustration \d/i.test(record.title) && !record.has_troubleshooting_table) {
    score -= 15;
  }

  for (const topic of IRRELEVANT_TOPICS) {
    if (hay.includes(topic)) score -= 35;
  }

  if (wantsImplement) {
    const hasImplementContext = IMPLEMENT_TERMS.test(hay);
    if (!hasImplementContext) score -= 60;

    if (/\b(left|right)\b/i.test(query) && !/\b(blade|tilt|ripper|implement|steer)\b/i.test(hay)) {
      score -= 40;
    }
  }

  if (/\b(blade.*tilt|tilt.*blade|blade tilt)\b/i.test(query)) {
    if (!/\b(blade|tilt|dual tilt|tilt cylinder|tilt solenoid|bulldozer|implement hyd)\b/i.test(hay)) {
      score -= 90;
    }
  }

  const matchedTokens = tokens.filter((t) => hay.includes(t)).length;
  if (matchedTokens < Math.ceil(tokens.length / 2)) score -= 20;

  return score;
}

export function searchRecords<T extends SearchableRecord>(
  records: T[],
  query: string,
  limit = 8,
): T[] {
  const tokens = tokenize(query);
  const bladeTiltQuery = /\b(blade.*tilt|tilt.*blade|blade tilt)\b/i.test(query);
  const startingQuery = /\b(not starting|won't start|not cranking|won't crank|cranks but)\b/i.test(query);
  const minScore = bladeTiltQuery ? 50 : startingQuery ? 20 : queryWantsImplement(query) ? 25 : 8;

  return records
    .filter((r) => r.body_text?.trim())
    .map((record) => ({record, score: scoreRecord(record, query, tokens)}))
    .filter((x) => x.score >= minScore)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((x) => x.record);
}

export function toContextRecords(records: SearchableRecord[]) {
  return records.map((r) => ({
    id: r.id ?? "",
    title: r.title,
    body_text: r.body_text,
    page_start: (r as {page_start?: number}).page_start,
    page_end: (r as {page_end?: number}).page_end,
    smcs: r.smcs ?? [],
    content_type: r.content_type ?? "",
    has_troubleshooting_table: r.has_troubleshooting_table ?? false,
    manual_type: r.manual_type ?? "",
    system: r.system ?? "",
  }));
}
