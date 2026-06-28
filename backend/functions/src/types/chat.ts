import {z} from "zod";

export const contextRecordSchema = z.object({
  id: z.string().min(1),
  title: z.string().optional(),
  body_text: z.string().min(1),
  page_start: z.number().int().optional(),
  page_end: z.number().int().optional(),
  smcs: z.array(z.string()).optional(),
  content_type: z.string().optional(),
  has_troubleshooting_table: z.boolean().optional(),
  manual_type: z.string().optional(),
  system: z.string().optional(),
});

export const chatMessageSchema = z.object({
  role: z.enum(["user", "assistant"]),
  content: z.string().min(1),
});

export const chatRequestSchema = z.object({
  machineId: z.string().min(1),
  machineName: z.string().optional(),
  message: z.string().min(1).max(4000),
  conversationHistory: z.array(chatMessageSchema).max(20).default([]),
  contextRecords: z.array(contextRecordSchema).min(1).max(15),
});

export type ContextRecord = z.infer<typeof contextRecordSchema>;
export type ChatRequest = z.infer<typeof chatRequestSchema>;

export type DiagnosticCheck = {
  rank: number;
  title: string;
  description: string;
  recordId: string;
  citation: {
    page?: string;
    smcs?: string;
    source?: string;
  };
};

export type ChatResponse = {
  reply: string;
  checks: DiagnosticCheck[];
  followUpQuestions: string[];
  citedRecordIds: string[];
};

export const aiResponseSchema = z.object({
  reply: z.string(),
  checks: z
    .array(
      z.object({
        rank: z.number().int().min(1).max(5),
        title: z.string(),
        description: z.string(),
        recordId: z.string(),
        citation: z
          .object({
            page: z.string().optional(),
            smcs: z.string().optional(),
            source: z.string().optional(),
          })
          .default({}),
      }),
    )
    .max(5),
  followUpQuestions: z.array(z.string()).max(3),
  citedRecordIds: z.array(z.string()),
});
