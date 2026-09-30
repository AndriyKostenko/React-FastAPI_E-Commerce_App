import { sessionManagaer } from "@/actions/getCurrentUser";
import Container from "@/components/ui/Container";
import FormWrap from "@/components/ui/FormWrap";
import LoginForm from "./LoginForm";
import type { SearchParams } from "@/types/auth";
import { AUTH_ERROR_MAX_LENGTH, AUTH_ERROR_PARAM, NEXTAUTH_ERROR_MESSAGES } from "@/utils/constants";

const firstValue = (value: string | string[] | undefined): string | undefined =>
    Array.isArray(value) ? value[0] : value;

/**
 * The message a failed sign-in left in the URL: our backend's own (set by the
 * signIn callback) wins; otherwise NextAuth's `error` code is translated.
 */
const resolveAuthError = (params: SearchParams): string | undefined => {
    const backendMessage = firstValue(params[AUTH_ERROR_PARAM]);
    if (backendMessage) return backendMessage.slice(0, AUTH_ERROR_MAX_LENGTH);
    const code = firstValue(params.error);
    if (code) return NEXTAUTH_ERROR_MESSAGES[code] ?? NEXTAUTH_ERROR_MESSAGES.Default;
    return undefined;
};

const Login = async ({ searchParams }: { searchParams: Promise<SearchParams> }) => {
    const currentUser = await sessionManagaer.getCurrentUser();
    const authError = resolveAuthError(await searchParams);
    return (
      <Container>
          <FormWrap>
              <LoginForm currentUser={currentUser} authError={authError}/>
          </FormWrap>
      </Container>
    );
}

export default Login;
