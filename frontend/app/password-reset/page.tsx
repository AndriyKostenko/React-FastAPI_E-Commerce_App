import Container from "@/components/ui/Container";
import FormWrap from "@/components/ui/FormWrap";
import ResetPasswordForm from "./ResetPasswordForm";

const PasswordReset = () => {
    return (
        <Container>
            <FormWrap>
                <ResetPasswordForm />
            </FormWrap>
        </Container>
    );
};

export default PasswordReset;
