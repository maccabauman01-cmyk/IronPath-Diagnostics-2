import {
  getManualRecords,
  getIllustrationsForRecord,
  getTablesForRecord,
  WatermelonManualRecord,
} from "./watermelon/store.js";
import {normalizeTableRows} from "./tableUtils.js";
import {scoreRecord, tokenize} from "../../../shared/search.js";

export type SearchHit = {
  recordId: string;
  score: number;
  title: string;
  system: string;
  manual_type: string;
  page_start: number;
  page_end: number;
  content_type: string;
  has_troubleshooting_table: boolean;
  snippet: string;
};

function snippet(text: string, max = 220): string {
  const clean = text.replace(/\s+/g, " ").trim();
  if (clean.length <= max) return clean;
  return `${clean.slice(0, max)}…`;
}

export function searchMachine(
  machineId: string,
  query: string,
  limit = 8,
): SearchHit[] {
  const recordMap = getManualRecords(machineId);
  const tokens = tokenize(query);
  const bladeTiltQuery = /\b(blade.*tilt|tilt.*blade|blade tilt)\b/i.test(query);
  const startingQuery = /\b(not starting|won't start|not cranking|won't crank|cranks but)\b/i.test(query);
  const minScore = bladeTiltQuery ? 50 : startingQuery ? 20 : /\b(blade|ripper|tilt|implement|bucket|boom)\b/i.test(query) ? 25 : 8;

  const hits: SearchHit[] = [];
  for (const record of recordMap.values()) {
    if (!record.body_text?.trim()) continue;

    const score = scoreRecord(record, query, tokens);
    if (score < minScore) continue;

    hits.push({
      recordId: record.id,
      score,
      title: record.title,
      system: record.system,
      manual_type: record.manual_type,
      page_start: record.page_start,
      page_end: record.page_end,
      content_type: record.content_type,
      has_troubleshooting_table: record.has_troubleshooting_table,
      snippet: snippet(record.body_text),
    });
  }

  hits.sort((a, b) => b.score - a.score);
  return hits.slice(0, limit);
}

export function searchToContext(machineId: string, hits: SearchHit[]) {
  const recordMap = getManualRecords(machineId);
  return hits
    .map((hit) => recordMap.get(hit.recordId))
    .filter((r): r is WatermelonManualRecord => Boolean(r?.body_text?.trim()))
    .map((r) => ({
      id: r.id,
      title: r.title,
      body_text: r.body_text,
      page_start: r.page_start,
      page_end: r.page_end,
      smcs: r.smcs,
      content_type: r.content_type,
      has_troubleshooting_table: r.has_troubleshooting_table,
      manual_type: r.manual_type,
      system: r.system,
    }));
}

export function enrichHitsWithAssets(machineId: string, hits: SearchHit[]) {
  return hits.map((hit) => {
    const illustrations = getIllustrationsForRecord(machineId, hit.recordId);
    const tables = getTablesForRecord(machineId, hit.recordId);
    return {
      ...hit,
      illustrations: illustrations.slice(0, 5).reduce<
        Array<{id: string; label: string; image_path: string; content_hash?: string}>
      >((acc, i) => {
        const key = i.content_hash ?? i.image_path;
        if (acc.some((x) => (x.content_hash ?? x.image_path) === key)) return acc;
        acc.push({
          id: i.id,
          label: i.label,
          image_path: i.image_path,
          content_hash: i.content_hash,
        });
        return acc;
      }, []).slice(0, 3),
      tables: tables.map((t) => {
        const rows = normalizeTableRows(t.columns, t.rows as unknown[]);
        const title =
          (t as {title?: string}).title ||
          (t.table_id.startsWith("Procedure:")
            ? t.table_id.replace(/^Procedure:\s*/, "")
            : undefined);
        return {
          table_id: t.table_id,
          title,
          type: t.type,
          columns: t.columns,
          rows,
          rowCount: rows.length,
        };
      }).filter((t) => t.rowCount <= 30),
    };
  });
}

export function getRecordDetail(machineId: string, recordId: string) {
  const record = getManualRecords(machineId).get(recordId);
  if (!record) return null;

  return {
    ...record,
    illustrations: getIllustrationsForRecord(machineId, recordId),
    tables: getTablesForRecord(machineId, recordId),
  };
}
