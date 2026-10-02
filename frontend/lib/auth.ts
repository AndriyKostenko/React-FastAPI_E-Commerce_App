import { AuthOptions, User } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import GoogleProvider from "next-auth/providers/google";
import { settings } from "@/lib/config";
import { ApiError } from "@/lib/api-error";
import { AUTH_ERROR_PARAM, AUTH_ERROR_MAX_LENGTH } from "@/utils/constants";

const LOGIN_FALLBACK = "Sign-in failed. Please try again.";
const GOOGLE_FALLBACK = "Google sign-in failed. Please try again.";

/** /login with a message the page shows as a toast; truncated to keep the URL sane. */
const loginErrorUrl = (message: string): string =>
    `/login?${AUTH_ERROR_PARAM}=${encodeURIComponent(message.slice(0, AUTH_ERROR_MAX_LENGTH))}`;

// adding jwt, user role and token expiry to the User object
interface CustomUser extends User {
    id: string;
    jwt: string;
    role: string;
    token_expiry: number;
}

declare module "next-auth" {
    interface Session {
        jwt: string;
        role: string;
        token_expiry: number;
        user: {
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
    // Used after email activation — the backend already verified identity, so we just validate
    // the returned token via /me before creating a session (prevents forgery).
    CredentialsProvider({
        id: "activation-token",
        name: "ActivationToken",
        credentials: {
            access_token: {},
            user_role: {},
            token_expiry: {},
            user_id: {},
            email: {},
        },
        async authorize(credentials) {
            if (!credentials?.access_token) return null;
            try {
                const res = await fetch(settings.api.endpoints.me, {
                    headers: { Authorization: `Bearer ${credentials.access_token}` },
                });
                if (!res.ok) return null;
                return {
                    id: credentials.user_id,
                    email: credentials.email,
                    jwt: credentials.access_token,
                    role: credentials.user_role,
                    token_expiry: Number(credentials.token_expiry),
                } as CustomUser;
            } catch {
                return null;
            }
        },
    }),
    CredentialsProvider({
        name: "Credentials",
        credentials: {
            email: { label: "Email", type: "email" },
            password: { label: "Password", type: "password" },
        },
        async authorize(credentials) {
            if (!credentials?.email || !credentials?.password) {
                throw new Error('Invalid email or password!');
            }

            const formData = new URLSearchParams();
            formData.append('username', credentials.email);
            formData.append('password', credentials.password);

            let response: Response;
            try {
                response = await fetch(settings.api.endpoints.authLogin, {
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
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

            const data = await response.json();

            // access_token is returned in the body by the gateway (alongside the HttpOnly cookie).
            // refresh_token is cookie-only and never exposed here.
            const jwt = data['access_token'];
            const role = data['user_role'];
            const token_expiry = data['token_expiry'];
            const userId = data['user_id'];

            if (!jwt) {
                console.error('authorize(): no access_token in response body');
                throw new Error(LOGIN_FALLBACK);
            }

            return { id: userId, email: credentials.email, jwt, role, token_expiry } as CustomUser;
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
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id_token: idToken }),
                });

                if (!response.ok) throw await ApiError.fromResponse(response, GOOGLE_FALLBACK);

                const data = await response.json();

                // Attach backend data to account so the jwt callback can pick it up
                (account as Record<string, unknown>).backendJwt = data['access_token'];
                (account as Record<string, unknown>).backendRole = data['user_role'];
                (account as Record<string, unknown>).backendTokenExpiry = data['token_expiry'];
                (account as Record<string, unknown>).backendUserId = data['user_id'];
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
        if (account?.provider === 'google' && (account as Record<string, unknown>).backendJwt) {
            return {
                ...token,
                id: (account as Record<string, unknown>).backendUserId,
                jwt: (account as Record<string, unknown>).backendJwt,
                role: (account as Record<string, unknown>).backendRole,
                token_expiry: (account as Record<string, unknown>).backendTokenExpiry,
            };
        }

        // Credentials sign-in
        if (user) {
            const customUser = user as CustomUser;
            return {
                ...token,
                id: customUser.id,
                jwt: customUser.jwt,
                role: customUser.role,
                token_expiry: customUser.token_expiry,
            };
        }
        return token;
    },

    session: async ({ session, token }) => {
        if (token) {
            session.jwt = token.jwt as string;
            session.role = token.role as string;
            session.token_expiry = token.token_expiry as number;
            session.user.id = token.id as string;
        }
        return session;
    },
  },
  secret: process.env.NEXTAUTH_SECRET || process.env.SECRET_KEY,
  pages: {
    signIn: '/login',
  },
};
