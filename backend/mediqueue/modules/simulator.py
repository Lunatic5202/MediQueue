"""Module 10 (live path helper): Synthetic event stream / replay.

Generates patients and vital-sign observations that flow through the SAME
ingestion pipeline as any other input. Useful for exercising ordering,
failure handling, and latency behavior. Synthetic data is not evidence of
clinical effectiveness.
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ..db import get_engine, utcnow
from ..pipeline import PipelineError, process_observation

logger = logging.getLogger("mediqueue.simulator")


@dataclass
class SimPatient:
    patient_id: str
    scenario: str
    arrival: datetime
    hr: float
    spo2: float
    sbp: float
    dbp: float
    temp: float
    start_minute: float = 0.0
    deterioration_onset_min: float | None = None


@dataclass
class ReplayState:
    running: bool = False
    n_patients: int = 0
    rate_per_min: float = 0.0
    scenario: str = "mixed"
    events_emitted: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_error: str | None = None
    task: asyncio.Task | None = None
    stop_flag: bool = False
    loop: asyncio.AbstractEventLoop | None = None


_state = ReplayState()


def get_replay_state() -> ReplayState:
    return _state


def _make_patient(scenario: str, now: datetime) -> SimPatient:
    pid = f"sim-{uuid.uuid4().hex[:12]}"
    hr = random.uniform(70, 95)
    spo2 = random.uniform(95, 99)
    sbp = random.uniform(105, 130)
    dbp = sbp - random.uniform(35, 55)
    temp = random.uniform(36.4, 37.3)
    onset = None
    if scenario == "sepsis_like":
        onset = random.uniform(2.0, 6.0)
    elif scenario == "respiratory_decline":
        onset = random.uniform(1.5, 5.0)
    return SimPatient(
        patient_id=pid,
        scenario=scenario,
        arrival=now,
        hr=hr,
        spo2=spo2,
        sbp=sbp,
        dbp=max(25.0, dbp),
        temp=temp,
        deterioration_onset_min=onset,
    )


def _advance(p: SimPatient, minutes_elapsed: float, rng: random.Random) -> list[dict[str, Any]]:
    """Produce the four vital observations for the current tick."""
    now = datetime.now(UTC)
    noise = lambda x, s: max(0.0, x + rng.gauss(0, s))  # noqa: E731

    hr, spo2, sbp, temp = p.hr, p.spo2, p.sbp, p.temp
    if p.deterioration_onset_min is not None and minutes_elapsed >= p.deterioration_onset_min:
        t = minutes_elapsed - p.deterioration_onset_min
        if p.scenario == "sepsis_like":
            hr = p.hr + min(55.0, 1.4 * t)          # tachycardia
            temp = p.temp + min(3.0, 0.06 * t)       # fever
            spo2 = p.spo2 - min(12.0, 0.22 * t)      # desaturation
            sbp = p.sbp - min(40.0, 0.7 * t)         # hypotension
        elif p.scenario == "respiratory_decline":
            spo2 = p.spo2 - min(15.0, 0.35 * t)
            hr = p.hr + min(35.0, 0.8 * t)
            temp = p.temp
            sbp = p.sbp - min(15.0, 0.2 * t)
    elif p.scenario == "stable" or p.deterioration_onset_min is None:
        hr, spo2, sbp, temp = (
            p.hr + rng.gauss(0, 1.2),
            p.spo2 + rng.gauss(0, 0.25),
            p.sbp + rng.gauss(0, 1.5),
            p.temp + rng.gauss(0, 0.03),
        )

    hr = min(220.0, max(30.0, noise(hr, 0.8)))
    spo2 = min(100.0, max(50.0, noise(spo2, 0.2)))
    sbp = min(260.0, max(45.0, noise(sbp, 1.0)))
    dbp = min(200.0, max(25.0, sbp - random.uniform(30, 55)))
    temp = min(43.0, max(28.0, noise(temp, 0.04)))

    device_ts = now
    common = {
        "patient_id": p.patient_id,
        "device_timestamp": device_ts.isoformat(),
        "ingest_timestamp": now.isoformat(),
        "source_id": "simulator",
    }
    return [
        {**common, "vital_type": "heart_rate", "value": round(hr, 1), "unit": "bpm"},
        {**common, "vital_type": "spo2", "value": round(spo2, 1), "unit": "%"},
        {
            **common,
            "vital_type": "blood_pressure",
            "value": round(sbp, 1),
            "value_diastolic": round(dbp, 1),
            "unit": "mmHg",
        },
        {**common, "vital_type": "temperature", "value": round(temp, 2), "unit": "°C"},
    ]


async def start_replay(
    n_patients: int, rate_per_min: float, scenario: str, duration_seconds: float | None
) -> ReplayState:
    global _state
    if _state.running:
        raise RuntimeError("replay already running")
    _state = ReplayState(
        running=True,
        n_patients=n_patients,
        rate_per_min=rate_per_min,
        scenario=scenario,
        started_at=utcnow(),
    )
    _state.loop = asyncio.get_running_loop()
    _state.task = asyncio.create_task(_run(n_patients, rate_per_min, scenario, duration_seconds))
    return _state


def stop_replay() -> ReplayState:
    _state.stop_flag = True
    return _state


async def _run(
    n_patients: int, rate_per_min: float, scenario: str, duration_seconds: float | None
) -> None:
    rng = random.Random()
    scenarios = ["stable", "sepsis_like", "respiratory_decline"]
    now = datetime.now(UTC)
    pool: list[SimPatient] = []
    for i in range(n_patients):
        sc = scenario if scenario != "mixed" else scenarios[i % len(scenarios)]
        pool.append(_make_patient(sc, now))

    # Each tick emits one observation per active patient, spaced so that the
    # aggregate event rate approximates rate_per_min (events/minute total).
    per_patient_interval_s = max(1.0, (n_patients * 60.0) / max(rate_per_min, 0.1))
    elapsed = 0.0
    try:
        while not _state.stop_flag:
            if duration_seconds is not None and elapsed >= duration_seconds:
                break
            tick_start = asyncio.get_event_loop().time()
            for p in pool:
                events = _advance(p, elapsed, rng)
                await asyncio.to_thread(_deliver_batch, events)
                _state.events_emitted += len(events)
            elapsed += per_patient_interval_s / 60.0
            sleep_for = per_patient_interval_s - (asyncio.get_event_loop().time() - tick_start)
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
    except Exception as exc:  # noqa: BLE001
        _state.last_error = str(exc)
        logger.exception("synthetic replay failed")
    finally:
        _state.running = False
        _state.finished_at = utcnow()


def _deliver_batch(events: list[dict[str, Any]]) -> None:
    """Deliver a batch of synthetic observations through the live pipeline.

    Runs in a worker thread; WebSocket fan-out is scheduled back on the main
    event loop. Durable events (polling fallback) are written in-transaction
    by the pipeline itself.
    """
    from sqlalchemy.orm import Session

    from ..realtime import hub

    engine = get_engine()
    loop = _state.loop
    for payload in events:
        try:
            with Session(engine, expire_on_commit=False) as session:
                with session.begin():
                    result = process_observation(session, payload, actor="simulator")
                if result.events and loop is not None:
                    asyncio.run_coroutine_threadsafe(hub.broadcast(result.events), loop)
        except PipelineError as exc:
            logger.warning("simulator observation rejected: %s %s", exc.code, exc.message)
        except Exception:  # noqa: BLE001
            logger.exception("simulator delivery failed")
