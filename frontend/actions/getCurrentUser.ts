import { authOptions } from "@/pages/api/auth/[...nextauth]"
import { getServerSession } from "next-auth"


// to get the current user among all app we have to reate session with our currenly logged in user, 
// which will be detected in our authorize() function in auth0ptions
export async function getSession() {
    return await getServerSession(authOptions)
}



export async function getCurrentUser() {
    try {
        const session = await getSession()

        if(!session?.user?.email) {
            return null
        }
        // getting current user from current session
        const currentUser = session.user

        return currentUser;

    } catch (error: any) {
        return null
    }
}