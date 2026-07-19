// loadtest/search.js — M10 hardening: PRD Year-1 target "search p95 < 300ms".
//
// k6 was not available in the environment this suite was authored in
// (`which k6` empty) — loadtest/pyloadtest.py is the asyncio+httpx fallback
// that was actually run against the local stack; see loadtest/RESULTS.md.
// This script is the k6-native equivalent for whoever has k6 installed.
//
// Usage:
//   BASE_URL=http://localhost:8000 AUTH_COOKIE="vaultly_access=...; vaultly_refresh=..." \
//     k6 run loadtest/search.js
//
// AUTH_COOKIE: sign in once out-of-band (e.g. via curl -c) and paste the
// Cookie header value here — k6 VUs don't share a login flow by default and
// the search endpoint is auth-scoped to a vault.

import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const AUTH_COOKIE = __ENV.AUTH_COOKIE || "";
const QUERIES = ["acme", "warranty", "insurance", "receipt", "policy", "loadtest"];

export const options = {
  scenarios: {
    search: {
      executor: "constant-vus",
      vus: Number(__ENV.VUS || 10),
      duration: __ENV.DURATION || "30s",
    },
  },
  thresholds: {
    // PRD Year-1 gate: search p95 < 300ms.
    http_req_duration: ["p(95)<300"],
    http_req_failed: ["rate<0.01"],
  },
};

export default function () {
  const q = QUERIES[Math.floor(Math.random() * QUERIES.length)];
  const res = http.get(`${BASE_URL}/api/v1/search?q=${encodeURIComponent(q)}`, {
    headers: { Cookie: AUTH_COOKIE },
    tags: { name: "search" },
  });
  check(res, { "status is 200": (r) => r.status === 200 });
  sleep(0.2);
}
