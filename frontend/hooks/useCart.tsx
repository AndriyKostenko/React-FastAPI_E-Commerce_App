'use client';

import { CartProductType } from '@/app/product/[productId]/ProductDetails';
import { product } from '@/utils/product';
import { products } from '@/utils/products';
import { createContext, useState, useContext, useCallback } from 'react';


// to be fixed with more props
// if the cart is empty - null
type CartContextType = {
    cartTotalQty: number;
    cartProducts: CartProductType[] | null;
    handleAddProductToCart: (product: CartProductType) => void
};


// by default its null
export const CartContext = createContext<CartContextType | null>(null);

interface Props {
    [propName: string] : any
};


// providing all details in cart between components
// for now its able to accept any props
export const CartContextProvider = (props: Props) => {

    const [cartTotalQty, setCartTtotalQty] = useState(0);
    const [cartProducts, setCartProducts] = useState<CartProductType[] | null>(null)



    // adding products to cart
    const handleAddProductToCart = useCallback((product: CartProductType) => {
        setCartProducts((previousState) => {
            let updatedCart;

            if(previousState) {
                // looking for already existing product in the cart by ID
                // if it is - updating quantity respectivly
                const indexOfExistProduct = previousState.findIndex(prod => prod.id === product.id);
                if (indexOfExistProduct !== -1) {
                    previousState[indexOfExistProduct].quantity = product.quantity;
                    return [...previousState];
                }
                updatedCart = [...previousState, product]
            } else {
                updatedCart = [product]
            }

            return updatedCart;
        })
    }, [])

    // will be able to pass all different proprs like state for cartTotalQty, functions like add ropduct/remove product from cart
    const value = {
        cartTotalQty,
        cartProducts,
        handleAddProductToCart,
    }

    return <CartContext.Provider value={value} {...props}/>
};


// custom hook which must be used only within CartContextProvider
export const useCart = () => {
    const context = useContext(CartContext);

    if (context === null) {
        throw new Error('useCart must be used within a CartContextProvider')
    }
    
    return context;
};

