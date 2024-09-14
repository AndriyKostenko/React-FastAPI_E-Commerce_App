import { sessionManagaer } from "@/actions/getCurrentUser";
import Container from "../components/Container";
import FormWrap from "../components/FormWrap";
import RegisterForm from "./RegisterForm";


const Register = async () => {
    const currentUser = await sessionManagaer.getCurrentUser();
    return ( 
        <Container>
            <FormWrap>
                <RegisterForm currentUser={currentUser}/>
            </FormWrap>
        </Container>
     );
}
 
export default Register;
