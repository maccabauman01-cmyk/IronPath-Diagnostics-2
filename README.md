# IronPath Diagnostics

AI-guided mining equipment diagnostic assistant. Supports **D11T Dozer**, **785D Dump Truck**, and **EX3600-7 Hitachi Excavator**.

## Backend

Local dev API (port **8787**) + Firebase Cloud Functions for OpenAI chat.

```bash
cd backend
cp .env.example .env   # add OPENAI_API_KEY
npm install
npm run dev
```

Health check: `GET http://127.0.0.1:8787/health`

CLI test:

```bash
npm run ask -- d11t-dozer "Blade won't tilt left"
```

Dev login: `tech@ironpath.local` / `ironpath123`

## Repo layout

| Path | Purpose |
|------|---------|
| `backend/` | Dev server, Cloud Functions, Firebase config |
| `shared/` | Shared search scoring (used by backend + clients) |
| `pipeline/` | Manual PDF extraction and WatermelonDB seed builder |

Manual seed data lives in `data/` (not in this repo — run pipeline locally or sync separately).

## Environment

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Required for AI chat |
| `OPENAI_MODEL` | Dev default: `gpt-4o-mini`. Production: `gpt-4o` |
