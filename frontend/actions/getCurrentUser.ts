import { cookies } from "next/headers";
import type { JWT } from "next-auth/jwt";
import { SessionCookie } from "@/lib/session-cookie";

//to get the current user among all app we have to create session with our currently logged in user,
//which will be detected in our authorize() function in auth0ptions in app/middleware/NextAuth.ts

/** The signed-in user as the server knows them. The access token is part of it, and it never leaves the server. */
export interface CurrentSession {
  user: {
    id: string;
    email: string;
    name?: string | null;
    image?: string | null;
  };
  jwt: string;
  role: string;
  /** When the access token expires (unix seconds); the proxy refreshes it before then. */
  token_expiry: number;
  /** When the session itself ends: the refresh token's expiry (unix seconds). */
  session_expiry: number;
}

/** The raw session cookie by name, or undefined when the request has none. */
export type CookieReader = (name: string) => Promise<string | undefined>;

/** The token a raw session cookie holds, or null when it is not a valid session. */
export type TokenDecoder = (raw: string) => Promise<JWT | null>;

/**
 * Where a session manager gets its two inputs. Production uses the request's
 * cookies and next-auth's decoder. The dependencies are injected so a test can
 * control the order in which concurrent reads finish (see tests/session-race.test.ts).
 */
export interface SessionDependencies {
  readCookie: CookieReader;
  decodeToken: TokenDecoder;
}

const requestDependencies: SessionDependencies = {
  readCookie: async (name) => (await cookies()).get(name)?.value,
  decodeToken: (raw) => SessionCookie.decode(raw),
};

/**
 * Reads the signed-in user's session on the server.
 *
 * Stateless on purpose: the server handles many requests at once, so nothing
 * here may be stored on a shared object. Every call reads and decodes its own
 * request's session cookie and returns only what it needs.
 *
 * The access token lives in that encrypted cookie and is returned only to
 * server code (page rendering, the gateway proxy). It is never sent to the
 * browser: the session endpoint and the rendered HTML do not carry it.
 *
 * The request proxy (lib/session-proxy.ts) refreshes the access token before
 * anything here reads it; an expired one is still treated as signed out, which
 * is what a session whose refresh failed looks like.
 */
export class SessionManager {
  constructor(
    private readonly deps: SessionDependencies = requestDependencies,
  ) {}

  private async readSession(): Promise<CurrentSession | null> {
    const raw = await this.deps.readCookie(SessionCookie.cookieName());
    if (!raw) {
      return null;
    }

    let token: JWT | null;
    try {
      token = await this.deps.decodeToken(raw);
    } catch (error) {
      console.error("Error reading the session cookie:", error);
      return null;
    }
    if (
      !token ||
      typeof token.id !== "string" ||
      typeof token.jwt !== "string"
    ) {
      return null;
    }

    const session: CurrentSession = {
      user: {
        id: token.id,
        email: typeof token.email === "string" ? token.email : "",
        name: token.name,
        image: token.picture,
      },
      jwt: token.jwt,
      role: typeof token.role === "string" ? token.role : "",
      token_expiry: Number(token.token_expiry),
      // Sessions signed in before refresh tokens were kept end with their access token.
      session_expiry: Number(token.refresh_expiry ?? token.token_expiry),
    };

    if (this.isExpired(session)) {
      return null;
    }
    return session;
  }

  private isExpired(session: CurrentSession): boolean {
    const expiryUnixSeconds = session.token_expiry;
    if (!Number.isFinite(expiryUnixSeconds) || expiryUnixSeconds <= 0) {
      return false;
    }
    return Date.now() >= expiryUnixSeconds * 1000;
  }

  public async getCurrentUser() {
    const session = await this.readSession();
    if (!session?.user.email) {
      return null;
    }
    return session.user;
  }

  public async getCurrentUserId() {
    const session = await this.readSession();
    if (!session?.user.id) {
      return null;
    }
    return session.user.id;
  }

  /** For server code only: never pass the result to a client component or into a URL. */
  public async getCurrentUserJWT() {
    const session = await this.readSession();
    if (!session?.jwt) {
      return null;
    }
    return session.jwt;
  }

  /** When the session ends (unix seconds), for the page's sign-out timer. */
  public async getSessionExpiry() {
    const session = await this.readSession();
    if (!session?.session_expiry) {
      return null;
    }
    return session.session_expiry;
  }
}

export const sessionManagaer = new SessionManager();
