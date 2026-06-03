import { z } from "zod";

const schema = z.object({
  NODE_ENV: z.string().default("development"),
  PORT: z.coerce.number().default(8080),
  DATABASE_URL: z.string().url(),
  JWT_SECRET: z.string().min(32),
  OIDC_ISSUER: z.string().url(),
  OIDC_AUDIENCE: z.string().min(1),
  RP_ID: z.string().default("app.example.com"),
  RP_ORIGIN: z.string().url().default("https://app.example.com")
});

export const env = schema.parse(process.env);
