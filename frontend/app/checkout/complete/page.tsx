import { Suspense } from "react";
import Container from "@/components/ui/Container";
import FormWrap from "@/components/ui/FormWrap";
import CheckoutComplete from "./CheckoutComplete";

// Stripe's query parameters are read in the browser (useSearchParams), which
// needs the Suspense boundary; the server render does not use them.
const CheckoutCompletePage = () => {
    return (
        <div className="py-4 sm:p-8">
            <Container>
                <FormWrap>
                    <Suspense fallback={<p className="text-center text-slate-600">Checking your payment…</p>}>
                        <CheckoutComplete />
                    </Suspense>
                </FormWrap>
            </Container>
        </div>
    );
};

export default CheckoutCompletePage;
