import { authOptions } from "@/pages/api/auth/[...nextauth]"
import { getServerSession } from "next-auth"


// to get the current user among all app we have to create session with our currently logged in user, 
// which will be detected in our authorize() function in auth0ptions in pages/api/...nextauth
export async function getSession() {
    return await getServerSession(authOptions)
}



export async function getCurrentUser() {
    try {
        const session = await getSession()

        if(!session?.user?.email) {
            return null
        }
        // getting current user from session (all info) ,
        // we can get directly user from session like session.user but will be no 'role' info
        const currentUser = await fetch(`http://127.0.0.1:8000/get_user/${session.user.email}` ,{
            method: "GET",
            headers: { "Content-Type": "application/json"},
        });

        return currentUser.json();

    } catch (error: any) {
        return null
    }
}