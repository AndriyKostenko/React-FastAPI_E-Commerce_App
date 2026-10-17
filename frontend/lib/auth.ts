import { AuthOptions, DefaultSession, User } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import GoogleProvider from "next-auth/providers/google";
import { settings } from "@/lib/config";
import { ApiError } from "@/lib/api-error";
import { AUTH_ERROR_PARAM, AUTH_ERROR_MAX_LENGTH } from "@/utils/constants";
import { clientAddressHeaders } from "@/lib/client-address";
import { GatewayAuthClient, type BackendTokens, type SignedInBody } from "@/lib/gateway-auth-client";
import { SessionCookie } from "@/lib/session-cookie";

const LOGIN_FALLBACK = "Sign-in failed. Please try again.";
const GOOGLE_FALLBACK = "Google sign-in failed. Please try again.";

/** /login with a message the page shows as a toast; truncated to keep the URL sane. */
const loginErrorUrl = (message: string): string =>
    `/login?${AUTH_ERROR_PARAM}=${encodeURIComponent(message.slice(0, AUTH_ERROR_MAX_LENGTH))}`;

// Refresh and logout from the Next server; the proxy refreshes with its own client (proxy.ts).
const gatewayAuth = new GatewayAuthClient({
    refresh: settings.api.endpoints.authRefresh,
    logout: settings.api.endpoints.authLogout,
});

// The backend session kept in the encrypted session cookie, never in the browser.
interface CustomUser extends User {
    id: string;
    jwt: string;
    role: string;
    token_expiry: number;
    refresh_token: string;
    refresh_expiry: number;
}

/** The session fields for a signed-in response's tokens. */
const sessionTokens = (tokens: BackendTokens) => ({
    jwt: tokens.accessToken,
    token_expiry: tokens.accessExpiry,
    refresh_token: tokens.refreshToken,
    refresh_expiry: tokens.refreshExpiry,
});

// What the browser may see. The access and refresh tokens are deliberately not
// here: they stay in the encrypted session cookie and are read on the server
// only (actions/getCurrentUser.ts, lib/session-proxy.ts), so no script on the
// page can take them.
declare module "next-auth" {
    interface Session {
        role: string;
        user: DefaultSession["user"] & {
            id: string;
        };
    }
}

export const authOptions: AuthOptions = {
  providers: [
    GoogleProvider({
        clientId: process.env.GOOGLE_CLIENT_ID!,
        clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
    CredentialsProvider({
        name: "Credentials",
        credentials: {
            email: { label: "Email", type: "email" },
            password: { label: "Password", type: "password" },
            // The login form's Turnstile token, passed on to the gateway.
            captchaToken: { label: "Verification", type: "text" },
        },
        async authorize(credentials) {
            if (!credentials?.email || !credentials?.password) {
                throw new Error('Invalid email or password!');
            }

            const formData = new URLSearchParams();
            formData.append('username', credentials.email);
            formData.append('password', credentials.password);
            if (credentials.captchaToken) formData.append('captcha_token', credentials.captchaToken);

            let response: Response;
            try {
                response = await fetch(settings.api.endpoints.authLogin, {
                    method: "POST",
                    headers: {
                        ...(await clientAddressHeaders()),
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    body: formData.toString(),
                });
            } catch (error) {
                throw ApiError.from(error, LOGIN_FALLBACK);
            }

            // A thrown Error's message reaches signIn({redirect:false}) as `error`,
            // so the backend's own wording ("User is not verified", …) is shown.
            if (!response.ok) {
                const apiError = await ApiError.fromResponse(response, LOGIN_FALLBACK);
                console.error('authorize(): login failed', apiError.status, apiError.message);
                throw apiError;
            }

            const data = (await response.json()) as SignedInBody;

            // The access token comes in the body, the refresh token only as the
            // gateway's Set-Cookie, which this server call receives instead of
            // the browser. Both go into the encrypted session cookie.
            const tokens = gatewayAuth.tokensFrom(response, data);
            if (!tokens) {
                console.error('authorize(): the gateway sent no access token or no refresh cookie');
                throw new Error(LOGIN_FALLBACK);
            }

            const user: CustomUser = {
                id: data.user_id,
                email: credentials.email,
                role: data.user_role,
                ...sessionTokens(tokens),
            };
            return user;
        },
    }),
  ],
  callbacks: {
    // Exchange the Google ID token with the backend before persisting the session.
    // A failure returns a redirect URL, which cancels the sign-in entirely (no
    // half-authenticated state) and carries the backend's message to /login.
    signIn: async ({ account }) => {
        if (account?.provider === 'google') {
            const idToken = account.id_token;
            if (!idToken) return loginErrorUrl(GOOGLE_FALLBACK);

            try {
                const response = await fetch(settings.api.endpoints.googleLogin, {
                    method: 'POST',
                    headers: {
                        ...(await clientAddressHeaders()),
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ id_token: idToken }),
                });

                if (!response.ok) throw await ApiError.fromResponse(response, GOOGLE_FALLBACK);

                const data = (await response.json()) as SignedInBody;
                const tokens = gatewayAuth.tokensFrom(response, data);
                if (!tokens) throw new Error(GOOGLE_FALLBACK);

                // Attach backend data to account so the jwt callback can pick it up
                (account as Record<string, unknown>).backendTokens = tokens;
                (account as Record<string, unknown>).backendRole = data.user_role;
                (account as Record<string, unknown>).backendUserId = data.user_id;
            } catch (error) {
                const apiError = ApiError.from(error, GOOGLE_FALLBACK);
                console.error('signIn(google): backend exchange failed', apiError.status, apiError.message);
                return loginErrorUrl(apiError.message);
            }
        }
        return true;
    },

    jwt: async ({ token, user, account }) => {
        // Google sign-in: backend data was fetched in signIn callback and attached to account
        const backendTokens = (account as Record<string, unknown> | null | undefined)?.backendTokens as
            | BackendTokens
            | undefined;
        if (account?.provider === 'google' && backendTokens) {
            return {
                ...token,
                id: (account as Record<string, unknown>).backendUserId,
                role: (account as Record<string, unknown>).backendRole,
                ...sessionTokens(backendTokens),
            };
        }

        // Credentials sign-in
        if (user) {
            const customUser = user as CustomUser;
            return {
                ...token,
                id: customUser.id,
                role: customUser.role,
                jwt: customUser.jwt,
                token_expiry: customUser.token_expiry,
                refresh_token: customUser.refresh_token,
                refresh_expiry: customUser.refresh_expiry,
            };
        }
        return token;
    },

    session: async ({ session, token }) => {
        if (token) {
            session.role = token.role as string;
            session.user.id = token.id as string;
        }
        return session;
    },
  },
  events: {
    // Sign-out revokes the backend refresh token too, so the session cannot be
    // revived from it. The proxy never refreshes on NextAuth's own routes, so
    // this is the token the cookie holds right now.
    signOut: async ({ token }) => {
        if (typeof token?.refresh_token === 'string') {
            await gatewayAuth.logout(token.refresh_token);
        }
    },
  },
  secret: SessionCookie.secret(),
  session: { strategy: 'jwt', maxAge: SessionCookie.MAX_AGE_SECONDS },
  pages: {
    signIn: '/login',
  },
};
