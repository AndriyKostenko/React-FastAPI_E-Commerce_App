import { AuthOptions, User } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";




// adding jwt, user role and token expiry to the User object
interface CustomUser extends User {
    jwt: string;
    role: string;
    token_expiry: number;
}



// so.....during loggin/registerring of user we will be redirected here to authorize() function 
// where i do endpoint with getting of user by email, however it is suppose to be logic like with login to check by email and password but im sending back hashed_password
// so, its suppose to be refactored to got jwt token instead all of that and to compare it in authorize() function

export const authOptions: AuthOptions = { 
// Configure one or more authentication providers
  providers: [
    CredentialsProvider( {
        name: "Credentials",
        // The credentials are used to generate a suitable form on the sign in page.
        // You can specify whatever fields you are expecting to be submitted.
        // e.g. domain, username, password, 2FA token, etc.
        // we can pass any HTML attribute to the <input> tag through the object.
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
        // by default its returning an User object with id, name, email, image...but we a including there jwt to, thats why gining an error
        async authorize(credentials, req) {
            // here we write logic that takes the credentials and
            // submit to backend server and returns either a object representing a user or value
            // that is false/null if the credentials are invalid.
            // e.g. return { id: 1, name: 'J Smith', email: 'jsmith@example.com' }
            //console.log('Credentials inside of authorize():', [credentials?.email, credentials?.password])
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
                    throw new Error('Something went wrong')
                }

                const data = await response.json()
                //console.log('Data in authent: ', data)
                const jwt = data['access_token']
                const role = data['user_role']
                const token_expiry = data['token_expiry']

                // returning jwt token and credentials...by default its must to return only the User object or null but i do my implementetion with jwt token, role and tok_expiry and thats why we need to ovewrite the User object
                return { 
                    id: data["user_id"],
                    email: credentials.email,
                    jwt,
                    role,
                    token_expiry} as CustomUser;


            } catch (error) {
                return null;
            }
        }
    })
  ],
  // to make sure that our JWT is included in the session object, we have to add it to the callbacks object
  callbacks: {
    // adding jwt, user role and token expiry to the token
    jwt: async ({token, user}) => {
        if (user) {
            const customUser = user as CustomUser;

            return {
                ...token,
                jwt: customUser.jwt,
                role: customUser.role,
                token_expiry: customUser.token_expiry,

            };
        }
        return token;
    },


   

    // adding jwt, user role and token expriration time to the session
    session: async ({session, token}) => {
        if (token) {
            session.jwt = token.jwt as string;
            session.role = token.role as string;
            session.token_expiry = token.token_expiry as number;
        }
        return session
    }
  },
  pages: {
    signIn: '/login',
  },
  
};






