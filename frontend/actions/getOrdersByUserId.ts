const fetchOrderByUserId = async (userId: string, token: string | null): Promise<any[]> => {
	try {
		if (!token) {
			return [];
		}
		// adding cache: 'no-store' to prevent caching of the response
		const response = await fetch(`http://127.0.0.1:8000/api/v1/orders/user/${userId}`, {
			method: 'GET',
			cache: 'no-store',
			headers: {
				'Authorization': `Bearer ${token}`,
				'Content-Type': 'application/json'
			},
		});
		if (response.status === 404 || response.status === 401) {
			return [];
		}
		if (!response.ok) {
			console.error("Failed to fetch orders by user id:", response.status);
			return [];
		}
		const data = await response.json();

		const orders = Array.isArray(data) ? data : data.orders;

		return orders || [];

	} catch (error) {
		console.error(error)
		return [];
	}

};

export default fetchOrderByUserId;
