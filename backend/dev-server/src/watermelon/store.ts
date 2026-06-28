import {readFileSync, existsSync, readdirSync} from "node:fs";
import {join} from "node:path";
import {DATA_DIR} from "../config.js";

/** Same shape as data/{machine}/watermelon/manual_records.json */
export type WatermelonManualRecord = {
  id: string;
  machine: string;
  manual_type: string;
  system: string;
  source_file: string;
  page_start: number;
  page_end: number;
  smcs: string[];
  title: string;
  body_text: string;
  content_type: string;
  has_troubleshooting_table: boolean;
  page_image_path: string | null;
  fault_codes: unknown[];
};

export type WatermelonIllustration = {
  id: string;
  record_id: string;
  label: string;
  page: number;
  source_file: string;
  image_path: string;
  machine: string;
  content_hash?: string;
};

export type WatermelonTable = {
  table_id: string;
  record_id: string;
  page: number;
  source_file: string;
  type: string;
  columns: string[];
  rows: string[][];
};

export type WatermelonMachine = {
  id: string;
  name: string;
  record_count: number;
  illustration_count: number;
  table_count: number;
};

type MachineBundle = {
  manualRecords: Map<string, WatermelonManualRecord>;
  illustrationsByRecord: Map<string, WatermelonIllustration[]>;
  tablesByRecord: Map<string, WatermelonTable[]>;
};

const bundleCache = new Map<string, MachineBundle>();

function watermelonDir(machineId: string): string {
  return join(DATA_DIR, machineId, "watermelon");
}

function readJson<T>(path: string): T {
  return JSON.parse(readFileSync(path, "utf8")) as T;
}

function hasWatermelonBundle(machineId: string): boolean {
  return existsSync(join(watermelonDir(machineId), "manual_records.json"));
}

function loadBundle(machineId: string): MachineBundle {
  const cached = bundleCache.get(machineId);
  if (cached) return cached;

  const base = watermelonDir(machineId);
  const recordsPath = join(base, "manual_records.json");
  if (!existsSync(recordsPath)) {
    throw new Error(
      `No Watermelon seed for ${machineId}. Expected ${recordsPath}`,
    );
  }

  const manualRecords = readJson<WatermelonManualRecord[]>(recordsPath);
  const recordMap = new Map(manualRecords.map((r) => [r.id, r]));

  const illustrationsByRecord = new Map<string, WatermelonIllustration[]>();
  const illusPath = join(base, "illustrations.json");
  if (existsSync(illusPath)) {
    for (const ill of readJson<WatermelonIllustration[]>(illusPath)) {
      const list = illustrationsByRecord.get(ill.record_id) ?? [];
      list.push(ill);
      illustrationsByRecord.set(ill.record_id, list);
    }
  }

  const tablesByRecord = new Map<string, WatermelonTable[]>();
  const tablesPath = join(base, "tables.json");
  if (existsSync(tablesPath)) {
    for (const table of readJson<WatermelonTable[]>(tablesPath)) {
      const list = tablesByRecord.get(table.record_id) ?? [];
      list.push(table);
      tablesByRecord.set(table.record_id, list);
    }
  }

  const bundle: MachineBundle = {
    manualRecords: recordMap,
    illustrationsByRecord,
    tablesByRecord,
  };
  bundleCache.set(machineId, bundle);
  return bundle;
}

export function listWatermelonMachines(): WatermelonMachine[] {
  if (!existsSync(DATA_DIR)) {
    throw new Error(`Data folder not found: ${DATA_DIR}`);
  }

  const machines: WatermelonMachine[] = [];

  for (const entry of readdirSync(DATA_DIR, {withFileTypes: true})) {
    if (!entry.isDirectory() || !hasWatermelonBundle(entry.name)) continue;

    const machinesPath = join(watermelonDir(entry.name), "machines.json");
    if (existsSync(machinesPath)) {
      machines.push(...readJson<WatermelonMachine[]>(machinesPath));
    } else {
      machines.push({
        id: entry.name,
        name: entry.name,
        record_count: 0,
        illustration_count: 0,
        table_count: 0,
      });
    }
  }

  return machines.sort((a, b) => a.name.localeCompare(b.name));
}

export function getManualRecords(
  machineId: string,
): Map<string, WatermelonManualRecord> {
  return loadBundle(machineId).manualRecords;
}

export function getIllustrationsForRecord(
  machineId: string,
  recordId: string,
): WatermelonIllustration[] {
  return loadBundle(machineId).illustrationsByRecord.get(recordId) ?? [];
}

export function getTablesForRecord(
  machineId: string,
  recordId: string,
): WatermelonTable[] {
  return loadBundle(machineId).tablesByRecord.get(recordId) ?? [];
}

export function getMachineName(machineId: string): string {
  const machinesPath = join(watermelonDir(machineId), "machines.json");
  if (existsSync(machinesPath)) {
    const machines = readJson<WatermelonMachine[]>(machinesPath);
    const match = machines.find((m) => m.id === machineId);
    if (match) return match.name;
  }
  const manifestPath = join(watermelonDir(machineId), "manifest.json");
  if (existsSync(manifestPath)) {
    const manifest = readJson<{machine_name?: string}>(manifestPath);
    if (manifest.machine_name) return manifest.machine_name;
  }
  return machineId;
}

export function resolveIllustrationPath(
  machineId: string,
  imagePath: string,
): string {
  return join(DATA_DIR, machineId, imagePath);
}
