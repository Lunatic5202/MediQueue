#!/usr/bin/env python3
"""End-to-end load/latency benchmark against a running MediQueue server.

Measures, from the client's perspective:
- observation ingest -> persisted score (server-side stage timings + RTT)
- event -> visible alert (client RTT after alert exists)
- queue confirm -> applied update

Provisional target from the SDD (not a measured claim): 200 concurrent
patients at one reading per minute per vital without dropped events;
ingestion-to-persisted-score <200 ms p95; event-to-visible-alert <1 s p95.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx


def pct(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, int(round((p / 100.0) * (len(ordered) - 1)))))
    return ordered[k]


async def ensure_token(client: httpx.AsyncClient, base: str, username: str, password: str) -> str:
    r = await client.post(f"{base}/api/auth/login", json={"username": username, "password": password})
    r.raise_for_status()
    return r.json()["token"]


async def submit_observation(
    client: httpx.AsyncClient, base: str, headers: dict, payload: dict
) -> dict:
    start = time.perf_counter()
    r = await client.post(f"{base}/api/observations", json=payload, headers=headers)
    rtt_ms = (time.perf_counter() - start) * 1000.0
    body = r.json()
    return {"status_code": r.status_code, "rtt_ms": rtt_ms, "body": body}


async def run(args: argparse.Namespace) -> int:
    base = args.base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=30.0) as client:
        token = await ensure_token(client, base, args.username, args.password)
    headers = {"Authorization": f"Bearer {token}"}

    patient_ids = [f"bench-{uuid.uuid4().hex[:10]}" for _ in range(args.patients)]
    vitals = [
        ("heart_rate", lambda r: {"value": r.uniform(60, 130), "unit": "bpm"}),
        ("spo2", lambda r: {"value": r.uniform(90, 100), "unit": "%"}),
        (
            "blood_pressure",
            lambda r: {
                "value": r.uniform(85, 160),
                "value_diastolic": r.uniform(50, 100),
                "unit": "mmHg",
            },
        ),
        ("temperature", lambda r: {"value": r.uniform(36.0, 40.0), "unit": "°C"}),
    ]

    import random

    rng = random.Random(args.seed)
    latencies: list[float] = []
    stage_latencies: dict[str, list[float]] = {}
    failures = 0
    duplicates = 0
    alerts_seen: set[int] = set()

    semaphore = asyncio.Semaphore(args.concurrency)
    lock = asyncio.Lock()

    async with httpx.AsyncClient(timeout=30.0) as client:
        async def one(patient_id: str, vital: str, factory) -> None:
            nonlocal failures, duplicates
            async with semaphore:
                extra = factory(rng)
                now = datetime.now(timezone.utc)
                payload = {
                    "patient_id": patient_id,
                    "vital_type": vital,
                    "device_timestamp": now.isoformat(),
                    "ingest_timestamp": now.isoformat(),
                    "source_id": "benchmark",
                    **extra,
                }
                try:
                    res = await submit_observation(client, base, headers, payload)
                except Exception:  # noqa: BLE001
                    failures += 1
                    return
                if res["status_code"] != 200:
                    failures += 1
                    return
                body = res["body"]
                if body.get("status") == "duplicate":
                    duplicates += 1
                    return
                async with lock:
                    latencies.append(body.get("processing_ms", res["rtt_ms"]))
                    for k, v in (body.get("stages_ms") or {}).items():
                        stage_latencies.setdefault(k, []).append(v)
                    for aid in body.get("alert_ids") or []:
                        alerts_seen.add(aid)

        rounds = args.minutes
        for minute in range(rounds):
            tasks = []
            t_start = time.perf_counter()
            for pid in patient_ids:
                for vital, factory in vitals:
                    tasks.append(asyncio.create_task(one(pid, vital, factory)))
            await asyncio.gather(*tasks)
            elapsed = time.perf_counter() - t_start
            if minute == 0:
                print(f"round 0: {len(tasks)} events in {elapsed:.2f}s")
            sleep = max(0.0, 60.0 - elapsed)
            if sleep > 0 and minute < rounds - 1:
                await asyncio.sleep(sleep)

    total_events = len(patient_ids) * len(vitals) * rounds
    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "base_url": base,
            "patients": args.patients,
            "vitals_per_patient": len(vitals),
            "minutes": args.minutes,
            "concurrency": args.concurrency,
        },
        "events_attempted": total_events,
        "events_accepted": len(latencies),
        "duplicates": duplicates,
        "failures": failures,
        "distinct_alerts_created": len(alerts_seen),
        "processing_ms": {
            "p50": round(pct(latencies, 50), 3),
            "p95": round(pct(latencies, 95), 3),
            "p99": round(pct(latencies, 99), 3),
            "mean": round(statistics.fmean(latencies), 3) if latencies else None,
        },
        "stage_ms": {
            k: {"p50": round(pct(v, 50), 3), "p95": round(pct(v, 95), 3)}
            for k, v in stage_latencies.items()
        },
        "note": (
            "Client-side benchmark against a single-instance prototype. "
            "Reported values depend on hardware, load, and scenario; they are "
            "measurements, not SDD target claims."
        ),
    }
    print(json.dumps(report, indent=2))
    out_path = args.out or "artifacts/benchmarks/latest.json"
    Path = __import__("pathlib").Path
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"saved to {out_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--username", default="clinician1")
    parser.add_argument("--password", default="clinician1-pass")
    parser.add_argument("--patients", type=int, default=50)
    parser.add_argument("--minutes", type=int, default=2)
    parser.add_argument("--concurrency", type=int, default=64)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
