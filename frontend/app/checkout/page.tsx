import { getSession } from "next-auth/react";
import Container from "../components/Container";
import FormWrap from "../components/FormWrap";
import CheckoutClient from "./CheckoutClient";
import { getCurrentUserJWT } from "@/actions/getCurrentUser";



const Checkout = async () => {

    const currentUserJWT = await getCurrentUserJWT();

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