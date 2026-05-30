import { sessionManagaer } from "@/actions/getCurrentUser";
import Container from "@/components/ui/Container";
import FormWrap from "@/components/ui/FormWrap";
import LoginForm from "./LoginForm";


const Login = async () => {
    const currentUser = await sessionManagaer.getCurrentUser();
    return (
      <Container>
          <FormWrap>
              <LoginForm currentUser={currentUser}/>
          </FormWrap>
      </Container>
    );
}

export default Login;
