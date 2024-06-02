import { authOptions } from "@/pages/api/auth/[...nextauth]";
import { getServerSession } from "next-auth";
import { signOut } from "next-auth/react";
import toast from "react-hot-toast";




declare module "next-auth" {
    interface Session {
      jwt: string;
      role: string; // Adding jwt property to Session interface
      token_expiry: number; // Adding token exp property to Session interface
    }
  }

// to get the current user among all app we have to create session with our currently logged in user, 
// which will be detected in our authorize() function in auth0ptions in pages/api/...nextauth
export async function getSession() {
    return await getServerSession(authOptions)
}


export async function getCurrentUser() {
    try {
        const session = await getSession()
        console.log('Session data: ', session)
       
        if(!session?.user?.email) {
            return null
        }
        return session.user


    } catch (error: any) {
        console.error("Error fetching user data:", error);
        return null;
    }
}

export async function getCurrentUserJWT() {
    try {
        const session = await getSession()
        
        if(!session?.jwt) {
            return null
        }
        return session.jwt


    } catch (error: any) {
        console.error("Error fetching user data:", error);
        return null;
    }
}

export async function getCurrentUserRole() {
    try {
        const session = await getSession()
        
        if(!session?.role) {
            return null
        }
        return session.role


    } catch (error: any) {
        console.error("Error fetching user data:", error);
        return null;
    }
}


export async function getCurrentUserTokenExpiry() {
    try {
        const session = await getSession()
        
        if(!session?.token_expiry) {
            return null
        }
        return session.token_expiry


    } catch (error: any) {
        console.error("Error fetching user data:", error);
        return null;
    }
}
