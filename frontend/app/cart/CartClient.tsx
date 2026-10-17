"use client";

import { CartClientProps } from "@/types/cart";
import { useCart } from "@/hooks/useCart";
import { useCartPricing } from "@/hooks/useCartPricing";
import Link from "next/link";
import { MdArrowBack } from "react-icons/md";
import Heading from "@/components/ui/Heading";
import Button from "@/components/ui/Button";
import ItemContent from "./ItemContent";
import { formatPrice } from "@/utils/formatPrice";
import { useRouter } from "next/navigation";
import { useSessionExpiryCheck } from "@/hooks/useSessionExpiryCheck";

const CartClient: React.FC<CartClientProps> = ({currentUser, sessionExpiry}) => {
    const {cartProducts, handleClearCart, cartTotalAmount} = useCart();
    // The saved line prices can be stale; the server's replace them as soon as it answers.
    const { isPricing, serverSubtotal, changedLines, error: pricingError } = useCartPricing();

    const router = useRouter()

    useSessionExpiryCheck(sessionExpiry)

    if (!cartProducts || cartProducts.length === 0) {
        return (
            <div className="flex flex-col items-center">
                <div className="text-2xl">
                    Your cart is empty
                </div>
                <div>
                    <Link href={"/"} className="text-slate-500 flex items-center gap-1 mt-2">
                        <MdArrowBack></MdArrowBack>
                        <span>Start shopping</span>
                    </Link>
                </div>
            </div>
        )
    }
    return (
        <div>
            <Heading title="Shopping Cart" center></Heading>
            <div className="grid grid-cols-5 text-xs gap-4 pb-2 items-center mt-8">
                <div className="col-span-2 justify-self-start">PRODUCT</div>
                <div className="justify-self-center">PRICE</div>
                <div className="justify-self-center">QUANTITY</div>
                <div className="justify-self-end">TOTAL</div>
            </div>
            <div>
                {cartProducts && cartProducts.map((item) => {
                    return <ItemContent key={item.id} item={item} />
                })}
            </div>
            <div className="border-t-[1.5px] border-slate-200 py-4 flex justify-between gap-4">
                <div>
                    <Button label="Clear Cart" onClick={() => {handleClearCart()}} variant="keyboard" size="md"></Button>
                </div>
                <div className="text-sm flex flex-col gap-1 items-start">
                        <div className="flex justify-between w-full text-base font-semibold">
                            <span>Subtotal</span>
                            <span>{formatPrice(serverSubtotal ?? cartTotalAmount)}</span>
                        </div>
                        {isPricing && <p className="text-slate-500">Checking current prices…</p>}
                        {changedLines > 0 && (
                            <p className="text-slate-600">
                                {changedLines === 1 ? "A price has" : "Some prices have"} changed since you added
                                {changedLines === 1 ? " that item" : " these items"}; the cart shows the current ones.
                            </p>
                        )}
                        {pricingError && (
                            <p className="text-rose-500">
                                {pricingError} An item may no longer be available as it is; remove or change it to check out.
                            </p>
                        )}
                        <p className="text-slate-500">
                            Taxes abd shipping calculate at checkout
                        </p>

                        <Button label={currentUser ? 'Checkout' : 'Login to Checkout'}
                                variant="keyboard"
                                size="md"
                                onClick={() => router.push(currentUser ? '/checkout' : '/login')}>
                        </Button>

                        <Link href={"/"} className="text-slate-500 flex items-center gap-1 mt-2">
                            <MdArrowBack></MdArrowBack>
                            <span>Continue shopping</span>
                        </Link>
                </div>

            </div>
        </div>
     );
}
 
export default CartClient;
