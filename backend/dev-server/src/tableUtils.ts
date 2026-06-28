/** Normalize string[][] or object rows into a grid for API responses */
export function normalizeTableRows(
  columns: string[],
  rawRows: unknown[],
): string[][] {
  if (!columns.length || !rawRows.length) return [];

  const columnToKey = (column: string) =>
    column.toLowerCase().replace(/\s+/g, "_");

  return rawRows
    .map((raw) => {
      if (Array.isArray(raw)) {
        return columns.map((_, i) => String(raw[i] ?? "").trim());
      }
      if (raw && typeof raw === "object") {
        const obj = raw as Record<string, unknown>;
        const byKey = new Map<string, string>();
        for (const [k, v] of Object.entries(obj)) {
          byKey.set(k.toLowerCase(), String(v ?? "").trim());
        }
        return columns.map((col) => {
          const key = columnToKey(col);
          if (byKey.has(key)) return byKey.get(key)!;
          for (const [k, v] of byKey) {
            if (k.includes(key) || key.includes(k)) return v;
          }
          return "";
        });
      }
      return columns.map(() => String(raw ?? "").trim());
    })
    .filter((row) => row.some((cell) => cell.length > 0));
}
