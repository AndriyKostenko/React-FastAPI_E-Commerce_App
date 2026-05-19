import http from "k6/http";
import { check } from "k6";
import { Counter, Rate, Trend } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8001";
const TEST_TYPE = (__ENV.TEST_TYPE || "load").toLowerCase();

// Shared HTTP params — keep-alive + minimal headers for lowest overhead
const PARAMS = {
	headers: {
		"Connection": "keep-alive",
		"Accept": "application/json",
	},
	// Discard response body to eliminate JSON-parse overhead during throughput runs
	responseType: "none",
};

const profiles = {
	// Quick sanity check: 10 VUs, 30 s
	smoke: {
		scenarios: {
			users_smoke: {
				executor: "constant-vus",
				vus: 10,
				duration: "30s",
				gracefulStop: "5s",
			},
		},
	},

	// Graduated load: ramps from 50 → 300 RPS over ~5 min
	load: {
		scenarios: {
			users_load: {
				executor: "ramping-arrival-rate",
				startRate: 50,
				timeUnit: "1s",
				preAllocatedVUs: 100,
				maxVUs: 500,
				gracefulStop: "30s",
				stages: [
					{ target: 100, duration: "1m" },
					{ target: 200, duration: "2m" },
					{ target: 300, duration: "2m" },
					{ target: 0,   duration: "30s" },
				],
			},
		},
	},

	// High stress: pushes toward server limit (~500 RPS)
	stress: {
		scenarios: {
			users_stress: {
				executor: "ramping-arrival-rate",
				startRate: 100,
				timeUnit: "1s",
				preAllocatedVUs: 200,
				maxVUs: 1000,
				gracefulStop: "30s",
				stages: [
					{ target: 200, duration: "1m"  },
					{ target: 350, duration: "2m"  },
					{ target: 500, duration: "2m"  },
					{ target: 700, duration: "2m"  },
					{ target: 0,   duration: "30s" },
				],
			},
		},
	},

	// Sustained load for leak / degradation detection
	soak: {
		scenarios: {
			users_soak: {
				executor: "constant-arrival-rate",
				rate: 200,
				timeUnit: "1s",
				duration: "15m",
				preAllocatedVUs: 250,
				maxVUs: 600,
				gracefulStop: "30s",
			},
		},
	},

	// ─── MAX THROUGHPUT ─────────────────────────────────────────────────────────
	// Two parallel scenarios:
	//   • users_max  – ramps hard to find the saturation point
	//   • users_hold – holds the peak for 2 min to confirm stability
	// Every k6 performance knob is tuned for raw RPS:
	//   • no sleep, no think-time
	//   • responseType:"none" (body discarded at HTTP layer)
	//   • keep-alive connections reused across iterations
	//   • batch() fires 10 pipelined requests per VU iteration
	//   • noConnectionReuse:false (default) keeps TCP sockets open
	//   • discardResponseBodies:true at the options level as belt-and-suspenders
	max_throughput: {
		discardResponseBodies: true,
		scenarios: {
			// Phase 1 – climb fast to discover the ceiling
			users_max: {
				executor: "ramping-arrival-rate",
				startRate: 200,
				timeUnit: "1s",
				preAllocatedVUs: 400,
				maxVUs: 2000,
				gracefulStop: "0s",
				stages: [
					{ target: 500,  duration: "30s" },
					{ target: 1000, duration: "1m"  },
					{ target: 2000, duration: "1m"  },
					{ target: 3000, duration: "1m"  },
					{ target: 4000, duration: "1m"  },
					{ target: 0,    duration: "15s" },
				],
			},
			// Phase 2 – hold a high-but-stable rate to verify the server sustains it
			users_hold: {
				executor: "constant-arrival-rate",
				rate: 1500,
				timeUnit: "1s",
				duration: "2m",
				preAllocatedVUs: 400,
				maxVUs: 2000,
				gracefulStop: "0s",
				startTime: "4m45s", // starts after the ramp phases finish
			},
		},
	},
};

const selectedProfile = profiles[TEST_TYPE] || profiles.load;

// ── Custom metrics ────────────────────────────────────────────────────────────
const apiDuration    = new Trend("api_duration",    true);
const apiErrorRate   = new Rate("api_error_rate");
const apiStatusCodes = new Counter("api_status_codes");

export const options = {
	...selectedProfile,
	// Keep TCP connections alive between iterations
	noConnectionReuse: false,
	// Belt-and-suspenders: discard bodies globally (overridden per-request via responseType)
	discardResponseBodies: selectedProfile.discardResponseBodies ?? false,
	summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)", "p(99.9)"],
	thresholds: {
		http_req_failed:                       ["rate<0.05"],
		http_req_duration:                     ["p(95)<700", "p(99)<1500"],
		checks:                                ["rate>0.95"],
		api_error_rate:                        ["rate<0.05"],
		"http_req_duration{endpoint:users}":   ["p(95)<700"],
		"http_req_duration{endpoint:health}":  ["p(95)<250"],
	},
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function callEndpoint(endpoint, path, expectedStatuses = [200]) {
	const res = http.get(`${BASE_URL}${path}`, {
		...PARAMS,
		tags: { endpoint, test_type: TEST_TYPE },
	});

	const ok = check(res, {
		[`${endpoint} status is expected`]: (r) =>
			expectedStatuses.includes(r.status),
	});

	apiDuration.add(res.timings.duration, { endpoint });
	apiErrorRate.add(!ok, { endpoint });
	apiStatusCodes.add(1, { endpoint, status: String(res.status) });

	return res;
}

// For max_throughput: fire 10 requests in a single batch per VU iteration.
// k6 sends them over the same keep-alive connection in parallel, giving
// the highest possible request density per VU without extra overhead.
function batchUsersRequests() {
	const requests = Array.from({ length: 10 }, () => [
		"GET",
		`${BASE_URL}/api/v1/users?limit=10`,
		null,
		{ ...PARAMS, tags: { endpoint: "users", test_type: TEST_TYPE } },
	]);

	const responses = http.batch(requests);

	for (const res of responses) {
		const ok = check(res, {
			"users status is expected": (r) => r.status === 200,
		});
		apiDuration.add(res.timings.duration, { endpoint: "users" });
		apiErrorRate.add(!ok, { endpoint: "users" });
		apiStatusCodes.add(1, { endpoint: "users", status: String(res.status) });
	}
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────

export function setup() {
	console.log(`Running "${TEST_TYPE}" profile against ${BASE_URL}`);
}

export default function () {
	if (TEST_TYPE === "max_throughput") {
		batchUsersRequests();
	} else {
		callEndpoint("users", "/api/v1/users?limit=10");
	}
}
