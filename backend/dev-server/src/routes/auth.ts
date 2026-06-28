import type {Request, Response} from "express";
import {z} from "zod";
import {
  createDevToken,
  requireDevAuth,
  validateDevCredentials,
  verifyDevToken,
  type DevAuthedRequest,
} from "../auth.js";

const loginSchema = z.object({
  email: z.string().min(3),
  password: z.string().min(1),
});

export function handleLogin(req: Request, res: Response) {
  const parsed = loginSchema.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({error: "Invalid email or password"});
    return;
  }

  const {email, password} = parsed.data;
  if (!validateDevCredentials(email, password)) {
    res.status(401).json({error: "Invalid email or password"});
    return;
  }

  res.json({
    token: createDevToken(email),
    email,
  });
}

export function handleAuthMe(req: DevAuthedRequest, res: Response) {
  res.json({email: req.user!.email});
}

export {requireDevAuth, verifyDevToken};
