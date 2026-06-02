import http from "k6/http";
import { check } from "k6";

export const options = {
	stages: [
		{ duration: "1m", target: 50 },
		// { duration: "2m", target: 100 },
		// { duration: "2m", target: 200 },
		// { duration: "2m", target: 400 },
		// { duration: "1m", target: 0 },
	],

	thresholds: {
		http_req_failed: ["rate<0.01"],
		http_req_duration: ["p(95)<500"],
	},
};

export default function () {
	const res = http.get("http://127.0.0.1:8000/api/v1/products?limit=50");
	//const res = http.get("http://127.0.0.1:8002/api/v1/products?limit=50");
	//const res = http.get("http://127.0.0.1:8001/api/v1/users");

	check(res, {
		"status is 200": (r) => r.status === 200,
	});
}
