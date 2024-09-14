import NextAuth from "next-auth";
import { authOptions } from "@/app/middleware/NextAuth";

// NextAuth handler for getting user session through api calls
const handler = NextAuth(authOptions)

export { handler as GET, handler as POST };