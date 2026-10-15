
import Container from "@/components/ui/Container";
import FormWrap from "@/components/ui/FormWrap";
import CheckoutClient from "./CheckoutClient";
import { sessionManagaer } from "@/actions/getCurrentUser";
import { fetchDefaultAddress } from "@/actions/getAccount";


const Checkout = async () => {
    const currentUserJWT = await sessionManagaer.getCurrentUserJWT();
    // The shipping form starts from the saved default address, when there is one.
    const defaultAddress = currentUserJWT ? await fetchDefaultAddress(currentUserJWT) : null;
    return (
      <div className="py-4 sm:p-8">
          <Container>
              <FormWrap>
                  <CheckoutClient isSignedIn={Boolean(currentUserJWT)} defaultAddress={defaultAddress}/>
              </FormWrap>
          </Container>
      </div>
    );
}

export default Checkout;
