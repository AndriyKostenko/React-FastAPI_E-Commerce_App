"use client";

import { useRouter } from "next/navigation";
import { useCart } from "@/hooks/useCart";
import { CiShoppingCart } from "react-icons/ci";

// cart counter for icon
const CartCount = () => {
    const { cartTotalQty } = useCart();
    const router = useRouter();

    return (
        <div
            className="relative cursor-pointer"
            onClick={() => router.push("/cart")}
        >
            <CiShoppingCart className="text-2xl text-primary" />
            <span className="absolute -top-2 -right-2 bg-primary text-on-primary h-5 w-5 rounded-full flex items-center justify-center text-[11px] font-bold">
                {cartTotalQty}
            </span>
        </div>
    );
};

export default CartCount;
