import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { db } from "../db";
import { audit } from "../audit";
import { scoreLoginRisk, isStepUpRequired } from "../risk";

const extensionTokenSchema = z.object({
  code: z.string().min(8),
  redirectUri: z.string().url()
});

export async function authRoutes(app: FastifyInstance) {
  app.post("/auth/extension-token", async (request, reply) => {
    const body = extensionTokenSchema.parse(request.body);

    /*
      Production implementation:
      1. Exchange authorization code with OIDC provider using PKCE.
      2. Validate ID token issuer/audience/nonce with jose.
      3. Extract verified subject/email.
      4. Enforce passkey step-up when risk is high.

      This scaffold simulates a verified identity for local integration.
    */

    const email = "user@example.com";
    const oidcSub = `oidc:${email}`;

    const user = await db.user.upsert({
      where: { email },
      update: {},
      create: { email }
    });

    const riskScore = await scoreLoginRisk({
      userId: user.id,
      ip: request.ip,
      userAgent: request.headers["user-agent"]
    });

    await audit({
      userId: user.id,
      type: "auth.login.success",
      ip: request.ip,
      userAgent: request.headers["user-agent"],
      riskScore,
      metadata: {
        oidcSub,
        redirectUri: body.redirectUri,
        stepUpRequired: isStepUpRequired(riskScore)
      }
    });

    const accessToken = app.jwt.sign(
      {
        sub: user.id,
        email: user.email,
        acr: isStepUpRequired(riskScore) ? "urn:pm:step-up-required" : "urn:pm:normal"
      },
      {
        expiresIn: "15m"
      }
    );

    return reply.send({
      accessToken,
      expiresAt: Date.now() + 15 * 60 * 1000,
      stepUpRequired: isStepUpRequired(riskScore)
    });
  });
}
