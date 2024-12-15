'use client';

import { ProductProps } from "../interfaces/product";
import { OrderProps } from "../interfaces/order";
import { UserProps } from "../interfaces/user";
import { useEffect, useState } from "react";
import Heading from "../components/Heading";
import { formatPrice } from "@/utils/formatPrice";
import { formatNumber } from "@/utils/formatNumber";



interface SummaryProps {
    orders: OrderProps[];
    products: ProductProps[];
    users: UserProps[];
}

type SummaryDataType = {
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
		products: {
			label: 'Total Products',
			digit: 0
		},
		orders: {
			label: 'Total Orders',
			digit: 0
		},
		paidOrders: {
			label: 'Total Paid Orders',
			digit: 0
		},
		unpaidOrders: {
			label: 'Total Unpaid Orders',
			digit: 0
		},
		users: {
			label: 'Total Users',
			digit: 0
		}
	});

	useEffect(() => {
		// Update the summary data when orders, products, or users change
		setSummaryData((prev) => {
			// Create a copy of the previous state
			let tempData = {...prev};

			const totalSale = orders.reduce((acc, order) => {
				if (order.status === 'complete') {
					return acc + order.amount;
				} else {
					return acc;
				}
			}, 0);

			const paidOrders = orders.filter(order => order.status === 'complete')

			const unpaidOrders = orders.filter(order => order.status === 'pending')

			// Update the summary data
			tempData.sale.digit = totalSale;
			tempData.orders.digit = orders.length;
			tempData.paidOrders.digit = paidOrders.length;
			tempData.unpaidOrders.digit = unpaidOrders.length;
			tempData.products.digit = products.length;
			tempData.users.digit = users.length;

			return tempData;

	})}, [orders, products, users]);

	// Get the keys of the summary data as an array
	const summaryKeys = Object.keys(summaryData);


	return (
		<div className="max-2-[1150px] m-auto">
			<div className="mb-4 mt-8">
				<Heading title="Stats" center/>
			</div>

			<div className="grid grid-cols-2 gap-3 max-h-50vh overflow-y-auto">
				{summaryKeys && summaryKeys.map((key, index) => {
					return <div key={key} className="rounded-xl border-2 p-4 flex flex-col items-center gap-2 transition">
						<div className="text-xl md:text-4xl font-bold">
							{
								summaryData[key].label === 'Total Sale' ? 
								<>{formatPrice(summaryData[key].digit)}</> : 
								<>{formatNumber(summaryData[key].digit)}</>
							}
						</div>

						<div>
							{summaryData[key].label}
						</div>
					</div>

					
				})}
			</div>
		</div>
	);
};

export default Summary;