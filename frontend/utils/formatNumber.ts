export const formatNumber = (number: number): string => {
    return new Intl.NumberFormat('ca-CA').format(number);
}