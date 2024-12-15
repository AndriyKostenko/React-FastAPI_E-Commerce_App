import moment from "moment";
import fetchOrdersFromBackend from "./getOrders";

export default async function getGraphData(token: string) {
	try {
		// getting the start and end date for the last 7 days
		const startDate = moment().subtract(6, "days").startOf("day");
		const endDate = moment().endOf("day");

		console.log('startDate>>>>', startDate);
		console.log('endDate>>>>', endDate);
		
		// fetching the orders from the backend
		const data = await fetchOrdersFromBackend(token, startDate.toISOString(), endDate.toISOString());

		console.log('data from backend>>>>', data);

		// initializing an object to aggregate the data by day
		const aggregatedData: {
			[day: string]: {day: string, date: string, totalAmount: number}
		} = {};

		// creating a clone of the start date to iterate over each day
		const currentDate = startDate.clone();

		// iterate over each day from the start date to the end date
		while (currentDate <= endDate) {
			// format the current day to a string like Monday
			const day = currentDate.format("dddd");
			//console.log('day>>>>>',day, currentDate);

			// initialize the aggregated data for the day
			aggregatedData[day] = {
				day,
				date: currentDate.format("YYYY-MM-DD"),
				totalAmount: 0
			};

			// move to the next day
			currentDate.add(1, "day");
		}

		// calculate the total amount for each day by summing the amount of each order
		data.forEach((order: any) => {
			const day = moment(order.created_at).format("dddd");
			const amount = order.amount || 0;
			aggregatedData[day].totalAmount += amount;
		});

		// convert the aggregated object to an array and sort it by date
		const graphData = Object.values(aggregatedData).sort((a, b) => 
			moment(a.date).diff(moment(b.date))
		);

		return graphData;

	} catch (error: any) {
		console.error(error);
		return [];
	}
}
