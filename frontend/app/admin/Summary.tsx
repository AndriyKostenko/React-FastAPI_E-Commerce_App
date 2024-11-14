'use client';

import { ProductProps } from "../interfaces/product";
import { OrderProps } from "../interfaces/order";
import { UserProps } from "../interfaces/user";
import { useState } from "react";




interface SummaryProps {
    orders: OrderProps[];
    products: ProductProps[];
    users: UserProps[];
}

type SummaryDataType {
	[key: string]: {
		label: string;
		digit: number;
	}
}

 
const Summary:React.FC<SummaryProps> = ({orders, products, users}) => {
	const [summaryData, setSummaryData] = useState<SummaryDataType>({
		sale: {
			label: 'Total Sale',
			digit: 0
		},

	});
	return (
		<div>
		
		</div>
	);
};

export default Summary;