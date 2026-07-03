"""Network diagnostics for the pipeline's data endpoints.

Usage:
    python scripts/net_probe.py

Probes each endpoint with the exact user agent the pipeline uses and prints
timing per attempt. Run this from any environment (local machine, GitHub
Actions runner) when fetches start timing out, before changing any fetcher:
the 2026-07-03 incident showed the failure mode differs by network path and
user agent, and guessing wastes time (see VERIFICATION.md and README).
"""
from __future__ import annotations

import socket
import time
import urllib.request

BOT_UA = "market-regime-dashboard/1.0 (data pipeline)"
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

PROBES = [
    ("fredgraph bot-ua", "https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500", BOT_UA),
    ("fredgraph browser-ua", "https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500", BROWSER_UA),
    (
        "yahoo-q1 browser-ua",
        "https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?range=5d&interval=1d",
        BROWSER_UA,
    ),
    (
        "yahoo-q2 browser-ua",
        "https://query2.finance.yahoo.com/v8/finance/chart/%5EGSPC?range=5d&interval=1d",
        BROWSER_UA,
    ),
    ("multpl browser-ua", "https://www.multpl.com/shiller-pe", BROWSER_UA),
]


def main() -> int:
    for host in ("fred.stlouisfed.org", "query1.finance.yahoo.com"):
        try:
            addresses = sorted({ai[4][0] for ai in socket.getaddrinfo(host, 443)})
            print(f"resolve {host}: {addresses[:6]}")
        except OSError as error:
            print(f"resolve {host}: FAILED {error}")

    failures = 0
    for name, url, ua in PROBES:
        start = time.time()
        try:
            request = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(request, timeout=25) as response:
                size = len(response.read())
            print(f"{name}: OK {size:,} bytes in {time.time() - start:.1f}s")
        except Exception as error:  # noqa: BLE001 — diagnostics report everything
            failures += 1
            print(f"{name}: FAILED after {time.time() - start:.1f}s -> {type(error).__name__}: {error}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
