import type { FastifyRequest } from "fastify";

export type AuthUser = {
  sub: string;
  email: string;
};

export async function requireUser(request: FastifyRequest): Promise<AuthUser> {
  await request.jwtVerify();

  const user = request.user as {
    sub?: string;
    email?: string;
  };

  if (!user.sub || !user.email) {
    throw request.server.httpErrors.unauthorized("Invalid token");
  }

  return {
    sub: user.sub,
    email: user.email
  };
}
