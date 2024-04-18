'use client';

import { CartContextProvider } from "@/hooks/useCart";



// restricting to receive only components as a 'children'
interface CartProviderProps{
    children: React.ReactNode
}


// creating the provider for letting all other components  inside to access the current 'value' defined in CartContextProvier
const CartProvider: React.FC<CartProviderProps> = ({children}) => {
    return ( 
        <CartContextProvider> 
            {children} 
        </CartContextProvider>
    )
}
 
export default CartProvider; 