'use client';

import { CartProviderProps } from "@/types/components";
import { CartContextProvider } from "@/hooks/useCart";

const CartProvider: React.FC<CartProviderProps> = ({children}) => {
    return (
        <CartContextProvider>
            {children}
        </CartContextProvider>
    )
}
 
export default CartProvider;
