
// formatting price with stand JS methods
export const formatPrice = (amount: number) => {
    return new Intl.NumberFormat('en-CA', {
        style:'currency',
        currency: 'CAD'
    }).format(amount)
}