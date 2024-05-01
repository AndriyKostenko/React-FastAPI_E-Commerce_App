import NextAuth, { AuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";



// so.....during loggin/registerring of user we will be redirected here to authorize() function 
// where i do endpoint with getting of user by email, however it is suppose to be logic like with login to check by email and password but im sending back hashed_password
// so, its suppose to be refactored to got jwt token instead all of that and to compare it in authorize() function

export const authOptions: AuthOptions = {
// Configure one or more authentication providers
  providers: [
    CredentialsProvider( {
        name: "Credentials",
        credentials: {
            email: {
                label: "Email",
                type: "email",
            },
            password: {
                label: "Password",
                type: "password"
            }
     
        },
        async authorize(credentials, req) {
            if (!credentials?.email || !credentials?.password){
                throw new Error('Invalid email or password!')
            }

            try {
                const response = await fetch(`http://127.0.0.1:8000/get_user/${credentials.email}` ,{
                    method: "GET",
                    headers: {"Content-Type": "application/json"},
                });

                if (!response.ok) {
                    throw new Error('Invalid email')
                }
                

                const user = await response.json()
               

                return user


            } catch (error) {
                return null;
            }
        }
    })
  ],
  pages: {
    signIn: '/login',
  },
  session: {
    strategy: "jwt"
  },
  secret: process.env.NEXTAUTH_SECRET
}


export default NextAuth(authOptions);


