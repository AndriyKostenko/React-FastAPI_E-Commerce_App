import http from "k6/http";
import { check } from "k6";

export const options = {
	scenarios: {
		throughput: {
			executor: "constant-arrival-rate",
			rate: 1000,
			timeUnit: "1s",
			duration: "2m",
			preAllocatedVUs: 200,
			maxVUs: 1000,
		},
	},

	thresholds: {
		http_req_failed: ["rate<0.01"],
		http_req_duration: ["p(95)<500"],
	},
};

export default function () {
	const res = http.get("http://127.0.0.1:8000/api/v1/products?limit=50");

	check(res, {
		"status 200": (r) => r.status === 200,
	});
}
