import {defineString} from "firebase-functions/params";

/** Loaded from functions/.env.ironpath-diagnostics at deploy (no Secret Manager) */
export const openaiApiKeyParam = defineString("OPENAI_API_KEY");

export function getOpenAiKey(): string {
  return openaiApiKeyParam.value();
}
