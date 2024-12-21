'use client';

import { ProductProps } from '../app/interfaces/product';
import { createContext, useState, useContext, useCallback, useEffect } from 'react';
import { toast } from 'react-hot-toast';


// to be fixed with more props
// if the cart is empty - null
type CartContextType = {
    cartTotalQty: number;
    cartTotalAmount: number;
    cartProducts: ProductProps[] | null;
    handleAddProductToCart: (product: ProductProps) => void;
    handleRemoveProductFromCart: (product: ProductProps) => void;
    handleCartQtyIncrease: (product: ProductProps) => void;
    handleCartQtyDecrease: (product: ProductProps) => void;
    handleClearCart: () => void;
    paymentIntent: string | null;
    handleSetPaymentIntent: (val: string | null) => void;
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
    const [cartProducts, setCartProducts] = useState<ProductProps[] | null>(null);
    const [cartTotalAmount, setCartTottalAmount] = useState(0);
    const [paymentIntent, setPaymentIntent] = useState<string | null>(null)

    console.log('Cart Products in CartComntextProvider:',cartProducts)



    // getting items from local storage
    useEffect(() => {
        const cartItems: any | null = localStorage.getItem('eShopCartItems');
        const Products: ProductProps[] | null = cartItems ? JSON.parse(cartItems) : null;

        // updating payment intent in loal storage after it has been created
        const eShopPaymentIntent: string | null = localStorage.getItem('eShopPaymentIntent')
        let paymentIntent: string | null = null;
        try {
            paymentIntent = eShopPaymentIntent ? JSON.parse(eShopPaymentIntent) : null;
        } catch (error) {
            console.error('Error parsing paymentIntent from localStorage:', error);
        }
        
        setCartProducts(Products);
        setPaymentIntent(paymentIntent);
    }, [])

    // counting of total price and quantity iduring changing of products in cart
    useEffect(() => {

        // starting function on every update of products in cart
        const getTotals = () => {

            if (cartProducts) {
                const {total, qty} = cartProducts?.reduce((accumulator, item) => {
                    const itemTotal = item.price * item.quantity
    
                    accumulator.total += itemTotal
                    accumulator.qty += item.quantity
    
                    return accumulator
                }, {
                    total: 0,
                    qty: 0
                }
            );

            setCartTtotalQty(qty);
            setCartTottalAmount(total);

            };
        }


        getTotals()
    }, [cartProducts])


    // adding products to cart
    const handleAddProductToCart = useCallback((product: ProductProps) => {
        setCartProducts((previousState) => {
            let updatedCart;

            if (previousState) {
                // looking for already existing product in the cart by ID
                // if it is - updating quantity respectivly
                const indexOfExistProduct = previousState.findIndex(prod => prod.id === product.id);
                if (indexOfExistProduct !== -1) {

                    previousState[indexOfExistProduct].quantity = product.quantity;
                    //updating prev. state
                    updatedCart = [...previousState];
                } else {
                    updatedCart = [...previousState, product];
                }
            } else {
                updatedCart = [product]
                console.log('Cart is updated with product:', product)
            }

            localStorage.setItem('eShopCartItems', JSON.stringify(updatedCart));
            return updatedCart;
        })
        // info icon after adding the product
        toast.success('Product added to cart');
        console.log('product added to cart');

    }, [])

    // removing products from cart
    const handleRemoveProductFromCart = useCallback((product: ProductProps) => {
        
        if (cartProducts) {
            const filteredProducts = cartProducts.filter((item) => {
                return item.id !== product.id
            })

            setCartProducts(filteredProducts)
            toast.success('Product removed')
            // pushing items into local storage to save them during re-loading
            localStorage.setItem('eShopCartItems', JSON.stringify(filteredProducts));

        }
    }, [cartProducts])


    const handleCartQtyIncrease = useCallback((product: ProductProps) => {
        let updatedCart;

        // temp max quantity for product
        if (product.quantity === 99) {
            return toast.error('Ooops! Maximum number has reached.')
        }

        // check if already have products
        if (cartProducts) {
            updatedCart = [...cartProducts]

            // checking for same roduct id
            const existingIndexProduct = cartProducts.findIndex((item) => item.id === product.id)

            if (existingIndexProduct > -1) {
                updatedCart[existingIndexProduct].quantity = ++updatedCart[existingIndexProduct].quantity
            }

            setCartProducts(updatedCart);

            localStorage.setItem('eShopCartItems', JSON.stringify(updatedCart))
        }
    }, [cartProducts])


    const handleCartQtyDecrease = useCallback((product: ProductProps) => {
        let updatedCart;

        // temp max quantity for product
        if (product.quantity === 1) {
            return toast.error('Ooops! Minimum number has reached.')
        }

        // check if already have products
        if (cartProducts) {
            updatedCart = [...cartProducts]

            // checking for same roduct id
            const existingIndexProduct = cartProducts.findIndex((item) => item.id === product.id)

            if (existingIndexProduct > -1) {
                updatedCart[existingIndexProduct].quantity = --updatedCart[existingIndexProduct].quantity
            }

            setCartProducts(updatedCart);

            localStorage.setItem('eShopCartItems', JSON.stringify(updatedCart))
        }
    }, [cartProducts])

    const handleClearCart = useCallback(() => {
        setCartProducts(null)
        setCartTtotalQty(0)
        localStorage.removeItem('eShopCartItems')
    }, [cartProducts])


    // saving into starage and following new paymentintents
    const handleSetPaymentIntent = useCallback((val:string | null) => {
        setPaymentIntent(val)
        localStorage.setItem('eShopPaymentIntent', JSON.stringify(val))
    }, [paymentIntent])

    // will be able to pass all different proprs like state for cartTotalQty, functions like add ropduct/remove product from cart
    const value = {
        cartTotalQty,
        cartProducts,
        handleAddProductToCart,
        handleRemoveProductFromCart,
        handleCartQtyIncrease,
        handleCartQtyDecrease,
        handleClearCart,
        cartTotalAmount,
        paymentIntent,
        handleSetPaymentIntent
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

