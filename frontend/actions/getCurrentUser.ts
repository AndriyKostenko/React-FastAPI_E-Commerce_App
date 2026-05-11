
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/middleware/NextAuth";


// Adding jwt property to Session interface
declare module "next-auth" {
    interface Session {
      jwt: string;
      role: string; // Adding jwt property to Session interface
      token_expiry: number; // Adding token exp property to Session interface
    }
  }

//to get the current user among all app we have to create session with our currently logged in user, 
//which will be detected in our authorize() function in auth0ptions in app/middleware/NextAuth.ts


//we are creating a session manager to get the current user from the session
class SessionManager {
    private session: any;

    constructor() {
        this.session = null;
    }

    private async fetchSession() {
        try {
            this.session = await getServerSession(authOptions);
        } catch (error) {
            console.error("Error fetching session data:", error);
            this.session = null;
        }
    }

    private isSessionExpired(): boolean {
        const rawExpiry = this.session?.token_expiry;
        if (!rawExpiry) {
            return false;
        }

        const expiryUnixSeconds = Number(rawExpiry);
        if (!Number.isFinite(expiryUnixSeconds)) {
            return false;
        }

        return Date.now() >= expiryUnixSeconds * 1000;
    }

    public async getCurrentUser() {
        await this.fetchSession();

        if (this.isSessionExpired()) {
            return null;
        }

        if (!this.session?.user?.email) {
            return null;
        }
        return this.session.user;
    }

    public async getCurrentUserId() {
        await this.fetchSession();

        if (this.isSessionExpired()) {
            return null;
        }

        if (!this.session?.user?.id) {
            return null;
        }
        return this.session.user.id;
    }

    public async getCurrentUserJWT() {
        await this.fetchSession();

        if (this.isSessionExpired()) {
            return null;
        }

        if (!this.session?.jwt) {
            return null;
        }
        return this.session.jwt;
    }

    public async getCurrentUserRole() {
        await this.fetchSession();

        if (this.isSessionExpired()) {
            return null;
        }

        if (!this.session?.role) {
            return null;
        }
        return this.session.role;
    }

    public async getCurrentUserTokenExpiry() {
        await this.fetchSession();

        if (this.isSessionExpired()) {
            return null;
        }

        if (!this.session?.token_expiry) {
            return null;
        }
        return this.session.token_expiry;
    }
}

export const sessionManagaer = new SessionManager();

