/** Machine-appropriate chat starter prompts. */

export const STARTER_PROMPTS: Record<string, string[]> = {
  "d11t-dozer": [
    "Blade won't tilt left",
    "Engine overheating",
    "Transmission slipping",
    "Implement lever not responding",
  ],
  "785d-dump-truck": [
    "Engine overheating",
    "Transmission slipping",
    "Air conditioning not cooling",
    "Brakes not holding on grade",
  ],
  "ex3600-7-excavator": [
    "Swing drift when holding position",
    "Hydraulic oil overheating",
    "Engine fails to start",
    "Bucket curl is slow",
  ],
};

export function starterPromptsForMachine(machineId: string): string[] {
  return (
    STARTER_PROMPTS[machineId] ?? [
      "Engine overheating",
      "Hydraulic system slow",
      "Warning light on dashboard",
      "Unusual noise during operation",
    ]
  );
}
