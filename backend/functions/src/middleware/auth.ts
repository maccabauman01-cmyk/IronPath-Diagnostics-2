import {Request, Response, NextFunction} from "express";
import {getAuth} from "firebase-admin/auth";
import {initializeApp, getApps} from "firebase-admin/app";

if (!getApps().length) {
  initializeApp();
}

export type AuthedRequest = Request & {
  user?: {uid: string; email?: string};
};

export async function requireAuth(
  req: AuthedRequest,
  res: Response,
  next: NextFunction,
): Promise<void> {
  const header = req.headers.authorization;
  if (!header?.startsWith("Bearer ")) {
    res.status(401).json({error: "Missing or invalid Authorization header"});
    return;
  }

  const token = header.slice("Bearer ".length).trim();
  if (!token) {
    res.status(401).json({error: "Missing bearer token"});
    return;
  }

  try {
    const decoded = await getAuth().verifyIdToken(token);
    req.user = {uid: decoded.uid, email: decoded.email};
    next();
  } catch (err) {
    console.warn("Auth verification failed:", err);
    res.status(401).json({error: "Invalid or expired token"});
  }
}
