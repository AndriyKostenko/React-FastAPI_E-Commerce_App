/**
 * k6 stress test — GET /api/v1/products/detailed?limit=50
 * Path: API Gateway (8000) → Product Service (8002)
 *
 * Usage:
 *   k6 run script.js                                          # load (default)
 *   k6 run -e TEST_TYPE=smoke   script.js                    # quick sanity
 *   k6 run -e TEST_TYPE=stress  script.js                    # push toward limit
 *   k6 run -e TEST_TYPE=soak    script.js                    # 15-min leak check
 *   k6 run -e TEST_TYPE=max_throughput script.js             # find ceiling
 *   k6 run -e BASE_URL=http://staging.example.com script.js  # override host
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Rate, Trend } from "k6/metrics";

const BASE_URL  = __ENV.BASE_URL  || "http://127.0.0.1:8000";
const TEST_TYPE = (__ENV.TEST_TYPE || "load").toLowerCase();
const LIMIT     = __ENV.LIMIT || "50";

const ENDPOINT_PATH = `/api/v1/products/detailed?limit=${LIMIT}`;

// Keep-alive + JSON accept — no auth needed (public endpoint)
const PARAMS = {
	headers: {
		"Connection":  "keep-alive",
		"Accept":      "application/json",
	},
	responseType: "none", // discard body for throughput runs; flip to "text" to inspect responses
};

// ── Load profiles ─────────────────────────────────────────────────────────────

const profiles = {
	// 10 VUs for 30 s — confirm the endpoint responds at all
	smoke: {
		scenarios: {
			products_smoke: {
				executor:     "constant-vus",
				vus:          10,
				duration:     "30s",
				gracefulStop: "5s",
			},
		},
	},

	// Realistic traffic ramp: 20 → 150 RPS over ~5 min
	// Product queries (with relations) are heavier than simple list endpoints,
	// so we use a gentler ramp than the users test.
	load: {
		scenarios: {
			products_load: {
				executor:         "ramping-arrival-rate",
				startRate:        20,
				timeUnit:         "1s",
				preAllocatedVUs:  80,
				maxVUs:           300,
				gracefulStop:     "30s",
				stages: [
					{ target: 50,  duration: "1m"  },
					{ target: 100, duration: "2m"  },
					{ target: 150, duration: "2m"  },
					{ target: 0,   duration: "30s" },
				],
			},
		},
	},

	// Stress — push past comfortable load to find failure mode
	stress: {
		scenarios: {
			products_stress: {
				executor:         "ramping-arrival-rate",
				startRate:        50,
				timeUnit:         "1s",
				preAllocatedVUs:  150,
				maxVUs:           600,
				gracefulStop:     "30s",
				stages: [
					{ target: 100, duration: "1m"  },
					{ target: 200, duration: "2m"  },
					{ target: 350, duration: "2m"  },
					{ target: 500, duration: "2m"  },
					{ target: 0,   duration: "30s" },
				],
			},
		},
	},

	// Soak — sustained moderate load to detect memory leaks / connection exhaustion
	soak: {
		scenarios: {
			products_soak: {
				executor:         "constant-arrival-rate",
				rate:             80,
				timeUnit:         "1s",
				duration:         "15m",
				preAllocatedVUs:  120,
				maxVUs:           300,
				gracefulStop:     "30s",
			},
		},
	},

	// Max throughput — two-phase: ramp hard, then hold peak to confirm stability
	max_throughput: {
		discardResponseBodies: true,
		scenarios: {
			products_max: {
				executor:         "ramping-arrival-rate",
				startRate:        100,
				timeUnit:         "1s",
				preAllocatedVUs:  300,
				maxVUs:           1500,
				gracefulStop:     "0s",
				stages: [
					{ target: 200,  duration: "30s" },
					{ target: 500,  duration: "1m"  },
					{ target: 1000, duration: "1m"  },
					{ target: 1500, duration: "1m"  },
					{ target: 2000, duration: "1m"  },
					{ target: 0,    duration: "15s" },
				],
			},
			// Hold a stable high rate after the ramp finishes
			products_hold: {
				executor:         "constant-arrival-rate",
				rate:             800,
				timeUnit:         "1s",
				duration:         "2m",
				preAllocatedVUs:  300,
				maxVUs:           1500,
				gracefulStop:     "0s",
				startTime:        "4m45s",
			},
		},
	},
};

const selectedProfile = profiles[TEST_TYPE] || profiles.load;

// ── Custom metrics ─────────────────────────────────────────────────────────────
const productsDuration  = new Trend("products_duration",   true);
const productsErrorRate = new Rate("products_error_rate");
const productsStatus    = new Counter("products_status_codes");

// ── Thresholds ─────────────────────────────────────────────────────────────────
// Products/detailed is a JOIN-heavy query — thresholds are looser than simple endpoints.
export const options = {
	...selectedProfile,
	noConnectionReuse:    false,
	discardResponseBodies: selectedProfile.discardResponseBodies ?? false,
	summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)", "p(99.9)"],
	thresholds: {
		http_req_failed:                          ["rate<0.01"],           // <1% errors
		http_req_duration:                        ["p(95)<1500", "p(99)<3000"], // JOIN queries are slower
		checks:                                   ["rate>0.99"],
		products_error_rate:                      ["rate<0.01"],
		"http_req_duration{endpoint:products}":   ["p(95)<1500"],
		"http_req_duration{endpoint:health}":     ["p(95)<200"],
	},
};

// ── Helpers ────────────────────────────────────────────────────────────────────

function fetchProducts() {
	const res = http.get(`${BASE_URL}${ENDPOINT_PATH}`, {
		...PARAMS,
		tags: { endpoint: "products", test_type: TEST_TYPE },
	});

	const ok = check(res, {
		"products: status 200":      (r) => r.status === 200,
		"products: no gateway error": (r) => r.status !== 502 && r.status !== 503,
		"products: responded < 2s":  (r) => r.timings.duration < 2000,
	});

	productsDuration.add(res.timings.duration, { endpoint: "products" });
	productsErrorRate.add(!ok, { endpoint: "products" });
	productsStatus.add(1, { endpoint: "products", status: String(res.status) });

	return res;
}

// Batch variant for max_throughput — 5 pipelined requests per VU iteration
function batchProducts() {
	const reqs = Array.from({ length: 5 }, () => [
		"GET",
		`${BASE_URL}${ENDPOINT_PATH}`,
		null,
		{ ...PARAMS, tags: { endpoint: "products", test_type: TEST_TYPE } },
	]);

	const responses = http.batch(reqs);

	for (const res of responses) {
		const ok = check(res, {
			"products batch: status 200": (r) => r.status === 200,
		});
		productsDuration.add(res.timings.duration, { endpoint: "products" });
		productsErrorRate.add(!ok, { endpoint: "products" });
		productsStatus.add(1, { endpoint: "products", status: String(res.status) });
	}
}

// ── Lifecycle ──────────────────────────────────────────────────────────────────

export function setup() {
	// Warm-up: single request to ensure the service is up before the test begins
	const res = http.get(`${BASE_URL}${ENDPOINT_PATH}`, PARAMS);
	if (res.status !== 200) {
		console.warn(`⚠  Warm-up failed: ${res.status} — is the stack running?`);
	} else {
		const body = res.body ? JSON.parse(res.body) : [];
		console.log(
			`✓  Warm-up OK | ${TEST_TYPE} profile | limit=${LIMIT} | ` +
			`returned ${Array.isArray(body) ? body.length : "?"} products | ` +
			`${res.timings.duration.toFixed(0)} ms`
		);
	}
}

export default function () {
	if (TEST_TYPE === "max_throughput") {
		batchProducts();
	} else {
		fetchProducts();
		// Small think-time on smoke/load/soak to simulate realistic browsing.
		// Removed on stress & max_throughput to maximise pressure.
		if (TEST_TYPE === "smoke" || TEST_TYPE === "load" || TEST_TYPE === "soak") {
			sleep(Math.random() * 0.5); // 0–500 ms jitter
		}
	}
}
