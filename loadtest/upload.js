// loadtest/upload.js — M10 hardening: PRD Year-1 target "upload < 2s".
//
// k6 was not available in the environment this suite was authored in
// (`which k6` empty) — loadtest/pyloadtest.py is the asyncio+httpx fallback
// that was actually run against the local stack; see loadtest/RESULTS.md.
// This script is the k6-native equivalent for whoever has k6 installed.
//
// Exercises the full upload "ticket flow" a client experiences: request a
// presigned ticket, PUT the bytes straight to S3/MinIO, mark it complete.
// The byte transfer itself is excluded from the threshold's intent (it scales
// with file size/client bandwidth, not API latency) but IS included in the
// measured http_req_duration for the ticket_flow tag, same as the Python
// driver's wall-clock measurement, so the two are comparable.
//
// Usage:
//   BASE_URL=http://localhost:8000 AUTH_COOKIE="vaultly_access=...; vaultly_refresh=..." \
//     k6 run loadtest/upload.js

import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const AUTH_COOKIE = __ENV.AUTH_COOKIE || "";

export const options = {
  scenarios: {
    upload: {
      executor: "constant-vus",
      vus: Number(__ENV.VUS || 10),
      duration: __ENV.DURATION || "30s",
    },
  },
  thresholds: {
    // PRD Year-1 gate: upload ticket flow p95 < 2000ms.
    "http_req_duration{step:ticket_flow}": ["p(95)<2000"],
    http_req_failed: ["rate<0.01"],
  },
};

export default function () {
  const fileName = `loadtest-${__VU}-${__ITER}.pdf`;
  const jsonHeaders = { "Content-Type": "application/json", Cookie: AUTH_COOKIE };

  const ticketRes = http.post(
    `${BASE_URL}/api/v1/documents/uploads`,
    JSON.stringify({ file_name: fileName, content_type: "application/pdf", size_bytes: 1024 }),
    { headers: jsonHeaders, tags: { step: "ticket_flow" } },
  );
  if (!check(ticketRes, { "ticket created": (r) => r.status === 201 })) {
    sleep(0.5);
    return;
  }
  const { document_id: documentId, upload_url: uploadUrl } = ticketRes.json();

  const putRes = http.put(uploadUrl, "x".repeat(1024), {
    headers: { "Content-Type": "application/pdf" },
    tags: { step: "ticket_flow" },
  });
  check(putRes, { "put succeeded": (r) => r.status === 200 });

  const completeRes = http.post(
    `${BASE_URL}/api/v1/documents/${documentId}/complete`,
    null,
    { headers: { Cookie: AUTH_COOKIE }, tags: { step: "ticket_flow" } },
  );
  check(completeRes, { "complete succeeded": (r) => r.status === 200 });

  // Clean up so the free-tier 25-document quota doesn't stall a long run.
  http.del(`${BASE_URL}/api/v1/documents/${documentId}`, null, { headers: { Cookie: AUTH_COOKIE } });

  sleep(0.2);
}
