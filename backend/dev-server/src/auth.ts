import {createHmac, timingSafeEqual} from "node:crypto";
import type {Request, Response, NextFunction} from "express";

/** Hardcoded dev credentials — override via backend/.env if needed */
export const DEV_AUTH_EMAIL =
  process.env.DEV_AUTH_EMAIL ?? "tech@ironpath.local";
export const DEV_AUTH_PASSWORD =
  process.env.DEV_AUTH_PASSWORD ?? "ironpath123";

const DEV_AUTH_SECRET =
  process.env.DEV_AUTH_SECRET ?? "ironpath-dev-jwt-secret";

const TOKEN_TTL_MS = 7 * 24 * 60 * 60 * 1000;

export type DevAuthedRequest = Request & {
  user?: {email: string};
};

function sign(payload: string): string {
  return createHmac("sha256", DEV_AUTH_SECRET).update(payload).digest("base64url");
}

export function createDevToken(email: string): string {
  const body = JSON.stringify({
    email,
    exp: Date.now() + TOKEN_TTL_MS,
  });
  const payload = Buffer.from(body, "utf8").toString("base64url");
  return `${payload}.${sign(payload)}`;
}

export function verifyDevToken(token: string): {email: string} | null {
  const parts = token.split(".");
  if (parts.length !== 2) return null;

  const [payload, sig] = parts as [string, string];
  const expected = sign(payload);

  try {
    const a = Buffer.from(sig);
    const b = Buffer.from(expected);
    if (a.length !== b.length || !timingSafeEqual(a, b)) return null;
  } catch {
    return null;
  }

  try {
    const data = JSON.parse(
      Buffer.from(payload, "base64url").toString("utf8"),
    ) as {email?: string; exp?: number};
    if (!data.email || !data.exp || data.exp < Date.now()) return null;
    return {email: data.email};
  } catch {
    return null;
  }
}

export function validateDevCredentials(
  email: string,
  password: string,
): boolean {
  return email === DEV_AUTH_EMAIL && password === DEV_AUTH_PASSWORD;
}

export function requireDevAuth(
  req: DevAuthedRequest,
  res: Response,
  next: NextFunction,
): void {
  const header = req.headers.authorization;
  if (!header?.startsWith("Bearer ")) {
    res.status(401).json({error: "Missing or invalid Authorization header"});
    return;
  }

  const user = verifyDevToken(header.slice("Bearer ".length).trim());
  if (!user) {
    res.status(401).json({error: "Invalid or expired token"});
    return;
  }

  req.user = user;
  next();
}
