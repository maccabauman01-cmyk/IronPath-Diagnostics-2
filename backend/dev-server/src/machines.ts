import {listWatermelonMachines, getMachineName} from "./watermelon/store.js";

export type MachineInfo = {
  id: string;
  name: string;
  recordCount: number;
  illustrationCount: number;
  tableCount: number;
  dataSource: "watermelon";
};

export function listMachines(): MachineInfo[] {
  return listWatermelonMachines().map((m) => ({
    id: m.id,
    name: m.name,
    recordCount: m.record_count,
    illustrationCount: m.illustration_count,
    tableCount: m.table_count,
    dataSource: "watermelon" as const,
  }));
}

export {getMachineName};
