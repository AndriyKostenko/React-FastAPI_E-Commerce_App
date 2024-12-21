import { ProductProps } from './product';

export interface OrderProps {
    id:                string;
    amount:            number;
    status:            string;
    date_created:      string;
    address_id:        string;
    user_id:           string;
    currency:          string;
    delivery_status:   string;
    payment_intent_id: string;
    items:             OrderItemProps[];
}


export interface OrderItemProps {
    id:         string;
    quantity:   number;
    order_id:   string;
    product_id: string;
    price:      number;
    product:    ProductProps;
}