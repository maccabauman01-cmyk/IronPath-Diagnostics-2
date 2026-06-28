import {config as loadEnv} from "dotenv";
import {resolve, dirname} from "node:path";
import {fileURLToPath} from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

// Load backend/.env before reading any env vars
loadEnv({path: resolve(__dirname, "../../.env")});

/** Repo data folder: Ai Minning/data */
export const DATA_DIR =
  process.env.DATA_DIR ??
  resolve(__dirname, "../../../data");

export const PORT = Number(process.env.PORT ?? 8787);

export const OPENAI_API_KEY = process.env.OPENAI_API_KEY ?? "";

/** Dev: gpt-4o-mini (~15x cheaper). Production Firebase uses gpt-4o unless set. */
export const OPENAI_MODEL = process.env.OPENAI_MODEL ?? "gpt-4o-mini";
