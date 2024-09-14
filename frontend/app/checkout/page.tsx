
import Container from "../components/Container";
import FormWrap from "../components/FormWrap";
import CheckoutClient from "./CheckoutClient";
import { sessionManagaer } from "@/actions/getCurrentUser";



const Checkout = async () => {

    const currentUserJWT = await sessionManagaer.getCurrentUserJWT();

    return ( 
    
    <div className="p-8">
            <Container>
                <FormWrap>
                    <CheckoutClient currentUserJWT={currentUserJWT}/>
                </FormWrap>
            </Container>

    </div> );
}
 
export default Checkout;