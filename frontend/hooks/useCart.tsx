'use client';

import { CartContextType } from '@/types/cart';
import { ProductProps } from '@/types/product';
import { createContext, useState, useContext, useCallback, useEffect } from 'react';
import { toast } from 'react-hot-toast';

export const CartContext = createContext<CartContextType | null>(null);

interface Props {
    [propName: string] : any
};

export const CartContextProvider = (props: Props) => {
    const [cartTotalQty, setCartTtotalQty] = useState(0);
    const [cartProducts, setCartProducts] = useState<ProductProps[] | null>(null);
    const [cartTotalAmount, setCartTottalAmount] = useState(0);
    const [paymentIntent, setPaymentIntent] = useState<string | null>(null)

    console.log('Cart Products in CartComntextProvider:',cartProducts)

    useEffect(() => {
        const cartItems: any | null = localStorage.getItem('eShopCartItems');
        const Products: ProductProps[] | null = cartItems ? JSON.parse(cartItems) : null;

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

    useEffect(() => {
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

    const handleAddProductToCart = useCallback((product: ProductProps) => {
        setCartProducts((previousState) => {
            let updatedCart;

            if (previousState) {
                const indexOfExistProduct = previousState.findIndex(prod => prod.id === product.id);
                if (indexOfExistProduct !== -1) {
                    previousState[indexOfExistProduct].quantity = product.quantity;
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
        toast.success('Product added to cart');
        console.log('product added to cart');

    }, [])

    const handleRemoveProductFromCart = useCallback((product: ProductProps) => {
        if (cartProducts) {
            const filteredProducts = cartProducts.filter((item) => {
                return item.id !== product.id
            })

            setCartProducts(filteredProducts)
            toast.success('Product removed')
            localStorage.setItem('eShopCartItems', JSON.stringify(filteredProducts));
        }
    }, [cartProducts])

    const handleCartQtyIncrease = useCallback((product: ProductProps) => {
        let updatedCart;

        if (product.quantity === 99) {
            return toast.error('Ooops! Maximum number has reached.')
        }

        if (cartProducts) {
            updatedCart = [...cartProducts]
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

        if (product.quantity === 1) {
            return toast.error('Ooops! Minimum number has reached.')
        }

        if (cartProducts) {
            updatedCart = [...cartProducts]
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

    const handleSetPaymentIntent = useCallback((val:string | null) => {
        setPaymentIntent(val)
        localStorage.setItem('eShopPaymentIntent', JSON.stringify(val))
    }, [paymentIntent])

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

export const useCart = () => {
    const context = useContext(CartContext);

    if (context === null) {
        throw new Error('useCart must be used within a CartContextProvider')
    }

    return context;
};
