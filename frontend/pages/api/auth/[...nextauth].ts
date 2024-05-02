import NextAuth, { AuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import GoogleProvider from "next-auth/providers/google";



// so.....during loggin/registerring of user we will be redirected here to authorize() function 
// where i do endpoint with getting of user by email, however it is suppose to be logic like with login to check by email and password but im sending back hashed_password
// so, its suppose to be refactored to got jwt token instead all of that and to compare it in authorize() function

export const authOptions: AuthOptions = {
// Configure one or more authentication providers
  providers: [
    GoogleProvider({
        clientId: process.env.GOOGLE_CLIENT_ID as string,
        clientSecret: process.env.GOOGLE_CLIENT_SECRET as string
    }),
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
        // built in function authorize() where im checking with an existing user in db by email
        async authorize(credentials, req) {

            console.log('Credentials inside of authorize():', [credentials?.email, credentials?.password])
            if (!credentials?.email || !credentials?.password){
                throw new Error('Invalid email or password!')
            }

            try {

                // params to send to form_data on backend
                const formData = new URLSearchParams();
                formData.append('username', credentials.email);
                formData.append('password', credentials.password);

                const response = await fetch(`http://127.0.0.1:8000/login` ,{
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                    body: formData.toString()
                });

                if (!response.ok) {
                    throw new Error('Invalid email')
                }
                

                const user = await response.json()
               
                console.log('User from authorize(): ', user)

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


