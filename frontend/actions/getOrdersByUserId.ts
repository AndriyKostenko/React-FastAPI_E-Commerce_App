const fetchOrderByUserId = async (userId: string, productId: string): Promise<any> => {
	try {
		// adding cache: 'no-store' to prevent caching of the response
		const response = await fetch(`http://127.0.0.1:8000/orders/user/${userId}`, {
			method: 'GET',
			cache: 'no-store',

		});
		if (!response.ok) {
			console.error("Failed to fetch order by id:", response.status);
			return null;
		}
		const orders = await response.json();
		const order = orders.find((order: any) => order.productId === productId);

		return order || null;

	} catch (error) {
		console.error(error)
		return null;
	}

};

export default fetchOrderByUserId;