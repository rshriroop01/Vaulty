#!/usr/bin/env python3
"""loadtest/pyloadtest.py — asyncio + httpx load test.

k6 is not installed in this environment (`which k6` came back empty), so this
is the fallback driver for the two PRD Year-1 latency targets M10 needs to
exercise. `loadtest/search.js` and `loadtest/upload.js` are the k6-native
equivalents (same scenarios, same thresholds) for whoever runs this with k6
available.

No new dependency: httpx is already a dev/test dependency of apps/api.

Scenarios:
  search   GET /api/v1/search?q=...                         target p95 < 300ms
  upload   POST /uploads -> PUT presigned -> POST /complete  target p95 < 2000ms
           ("the upload ticket flow" — the API-side latency a client
           experiences initiating and confirming an upload; the actual byte
           transfer goes straight to S3/MinIO, per ARCHITECTURE.md, and its
           duration depends on file size + client bandwidth, not this API)

Usage:
  .venv/bin/python loadtest/pyloadtest.py --base-url http://localhost:8000 \\
      --scenario both --vus 10 --duration 30
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import sys
import time
from dataclasses import dataclass, field

import httpx

SEARCH_QUERIES = ["acme", "warranty", "insurance", "receipt", "policy", "loadtest"]
THRESHOLDS_MS = {"search": 300.0, "upload": 2000.0}


@dataclass
class Sample:
    elapsed_ms: float
    ok: bool
    status: int


@dataclass
class ScenarioResult:
    name: str
    samples: list[Sample] = field(default_factory=list)

    @property
    def durations(self) -> list[float]:
        return [s.elapsed_ms for s in self.samples if s.ok]

    @property
    def error_count(self) -> int:
        return sum(1 for s in self.samples if not s.ok)


def percentile(data: list[float], p: float) -> float:
    if not data:
        return float("nan")
    ordered = sorted(data)
    k = (len(ordered) - 1) * (p / 100)
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


async def _signup(client: httpx.AsyncClient, base_url: str, email: str) -> None:
    resp = await client.post(
        f"{base_url}/api/v1/auth/signup",
        json={"name": "Load Test", "email": email, "password": "loadtest-pass-1"},
    )
    resp.raise_for_status()


async def _upload_one(
    client: httpx.AsyncClient, base_url: str, file_name: str, *, cleanup: bool
) -> float:
    """The full ticket flow: create a ticket, PUT the bytes to the presigned
    URL, mark it complete. Returns elapsed wall time in ms. Deletes the
    document afterward when `cleanup` is True, so repeated iterations don't
    run into the free-tier 25-document quota (app/core/quotas.py)."""
    body = {"file_name": file_name, "content_type": "application/pdf", "size_bytes": 1024}
    start = time.perf_counter()
    ticket_resp = await client.post(f"{base_url}/api/v1/documents/uploads", json=body)
    ticket_resp.raise_for_status()
    ticket = ticket_resp.json()
    put_resp = await client.put(
        ticket["upload_url"], content=b"x" * 1024, headers={"Content-Type": "application/pdf"}
    )
    put_resp.raise_for_status()
    complete_resp = await client.post(
        f"{base_url}/api/v1/documents/{ticket['document_id']}/complete"
    )
    complete_resp.raise_for_status()
    elapsed_ms = (time.perf_counter() - start) * 1000
    if cleanup:
        await client.delete(f"{base_url}/api/v1/documents/{ticket['document_id']}")
    return elapsed_ms


async def _seed_search_corpus(client: httpx.AsyncClient, base_url: str, count: int) -> None:
    for i in range(count):
        await _upload_one(
            client, base_url, f"loadtest-acme-warranty-receipt-{i}.pdf", cleanup=False
        )


async def run_search(base_url: str, vus: int, duration: float) -> ScenarioResult:
    result = ScenarioResult("search")
    async with httpx.AsyncClient(timeout=30) as client:
        await _signup(client, base_url, f"loadtest-search-{secrets.token_hex(4)}@example.com")
        await _seed_search_corpus(client, base_url, count=8)

        deadline = time.monotonic() + duration

        async def worker(vu_id: int) -> None:
            i = 0
            while time.monotonic() < deadline:
                q = SEARCH_QUERIES[(vu_id + i) % len(SEARCH_QUERIES)]
                start = time.perf_counter()
                try:
                    resp = await client.get(f"{base_url}/api/v1/search", params={"q": q})
                    result.samples.append(
                        Sample((time.perf_counter() - start) * 1000, resp.status_code == 200, resp.status_code)
                    )
                except httpx.HTTPError:
                    result.samples.append(Sample((time.perf_counter() - start) * 1000, False, 0))
                i += 1

        await asyncio.gather(*(worker(v) for v in range(vus)))
    return result


async def run_upload(base_url: str, vus: int, duration: float) -> ScenarioResult:
    result = ScenarioResult("upload")
    async with httpx.AsyncClient(timeout=30) as client:
        await _signup(client, base_url, f"loadtest-upload-{secrets.token_hex(4)}@example.com")

        deadline = time.monotonic() + duration

        async def worker(vu_id: int) -> None:
            i = 0
            while time.monotonic() < deadline:
                try:
                    elapsed_ms = await _upload_one(
                        client, base_url, f"loadtest-upload-{vu_id}-{i}.pdf", cleanup=True
                    )
                    result.samples.append(Sample(elapsed_ms, True, 200))
                except httpx.HTTPStatusError as exc:
                    result.samples.append(Sample(0.0, False, exc.response.status_code))
                except httpx.HTTPError:
                    result.samples.append(Sample(0.0, False, 0))
                i += 1

        await asyncio.gather(*(worker(v) for v in range(vus)))
    return result


def report(result: ScenarioResult) -> bool:
    durations = result.durations
    total = len(result.samples)
    p50, p95, p99 = (percentile(durations, p) for p in (50, 95, 99))
    threshold = THRESHOLDS_MS[result.name]
    passed = total > 0 and result.error_count == 0 and p95 < threshold
    print(f"\n== {result.name} ==")
    print(f"  requests: {total}  errors: {result.error_count}")
    if durations:
        print(f"  p50: {p50:.1f}ms  p95: {p95:.1f}ms  p99: {p99:.1f}ms")
    print(f"  threshold: p95 < {threshold:.0f}ms  ->  {'PASS' if passed else 'FAIL'}")
    return passed


async def main_async(args: argparse.Namespace) -> int:
    scenarios = ["search", "upload"] if args.scenario == "both" else [args.scenario]
    ok = True
    for name in scenarios:
        runner = run_search if name == "search" else run_upload
        result = await runner(args.base_url, args.vus, args.duration)
        ok = report(result) and ok
    return 0 if ok else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--scenario", choices=["search", "upload", "both"], default="both")
    parser.add_argument("--vus", type=int, default=10, help="concurrent virtual users")
    parser.add_argument("--duration", type=float, default=30.0, help="seconds per scenario")
    args = parser.parse_args()
    sys.exit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
