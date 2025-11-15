#!/usr/bin/env python3
"""Skeleton ML service that computes simple divergence scores."""
from __future__ import annotations

import argparse
import json
import logging
import math
import signal
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from jetson.common.service_health import ServiceHealthTracker, ServiceIdentity


DEFAULT_CONFIG_PATH = "jetson/ml_service/config.yaml"
DEFAULT_CANONICAL_FILENAME = "canonical_state.json"
DEFAULT_HISTORY_FILENAME = "history.json"
DEFAULT_OUTPUT_FILENAME = "divergence.json"


default_metrics = ["active_leds", "avg_activity", "error_count"]


@dataclass
class ServiceConfig:
    data_dir: Path
    canonical_state_filename: str
    history_filename: str
    output_filename: str
    poll_interval_seconds: float
    history_window_seconds: int
    baseline_days: int
    zscore_threshold: float
    log_level: str = "INFO"

    @property
    def canonical_path(self) -> Path:
        return self.data_dir / self.canonical_state_filename

    @property
    def history_path(self) -> Path:
        return self.data_dir / self.history_filename

    @property
    def output_path(self) -> Path:
        return self.data_dir / self.output_filename


class DivergenceModel:
    """Very simple z-score based divergence calculator."""

    def __init__(self, baseline_days: int, threshold: float) -> None:
        self._baseline_days = max(1, baseline_days)
        self._threshold = threshold

    def score(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not history:
            return {"score": 0.0, "level": "unknown"}
        latest = history[-1]
        metrics = self._extract_metrics(latest)
        baseline = self._compute_baseline(history)
        recommendations = self._generate_recommendations(latest, history)
        scores = {}
        for key in metrics:
            mean, stdev = baseline.get(key, (0.0, 0.0))
            value = metrics[key]
            if stdev <= 1e-6:
                z = 0.0
            else:
                z = abs(value - mean) / stdev
            scores[key] = {"value": value, "mean": mean, "stdev": stdev, "z": z}
        max_z = max((entry["z"] for entry in scores.values()), default=0.0)
        level = "normal"
        if max_z >= self._threshold:
            level = "divergent"
        elif max_z >= self._threshold * 0.5:
            level = "caution"
        return {"score": round(max_z, 3), "level": level, "metrics": scores, "recommendations": recommendations}

    def _extract_metrics(self, entry: Dict[str, Any]) -> Dict[str, float]:
        leds = entry.get("leds", [])
        active_leds = sum(1 for led in leds if (led.get("activity_level") or 0) > 0.3)
        avg_activity = sum(led.get("activity_level", 0.0) for led in leds) / max(len(leds), 1)
        error_count = sum(1 for led in leds if led.get("health") == "ERROR")
        return {
            "active_leds": active_leds,
            "avg_activity": avg_activity,
            "error_count": error_count,
        }

    def _compute_baseline(self, history: List[Dict[str, Any]]) -> Dict[str, tuple[float, float]]:
        metrics_series: Dict[str, List[float]] = {key: [] for key in default_metrics}
        cutoff = history[-1]["timestamp"] - self._baseline_days * 86400
        for entry in history:
            if entry.get("timestamp", 0) < cutoff:
                continue
            metrics = self._extract_metrics(entry)
            for key, value in metrics.items():
                metrics_series[key].append(value)
        baseline = {}
        for key, series in metrics_series.items():
            if not series:
                baseline[key] = (0.0, 0.0)
            elif len(series) == 1:
                baseline[key] = (series[0], 0.0)
            else:
                baseline[key] = (statistics.mean(series), statistics.pstdev(series))
        return baseline

    def _generate_recommendations(self, latest: Dict[str, Any], history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prototype hook: examine latest snapshot for simple action suggestions."""
        recommendations: List[Dict[str, Any]] = []
        leds = latest.get("leds", [])
        timestamp = latest.get("timestamp")

        # Example rule: if any blinds (type=blind) are open while rain is detected in context, suggest closing.
        context = latest.get("context") or {}
        rain_expected = context.get("rain_expected")
        for led in leds:
            if led.get("type") == "blind":
                position = led.get("activity_type")
                if rain_expected and position not in (None, "closed"):
                    recommendations.append({
                        "timestamp": timestamp,
                        "trigger": "rain_expected",
                        "target": led.get("name"),
                        "suggestion": "Close blinds",
                        "confidence": 0.7,
                        "status": "pending",
                    })

        # Example rule: if a LED is repeatedly ERROR at same time of day, suggest checking breaker.
        for led in leds:
            if led.get("health") == "ERROR":
                occurrences = [
                    entry for entry in history[-10:]
                    if any(
                        l.get("name") == led.get("name") and l.get("health") == "ERROR"
                        for l in entry.get("leds", [])
                    )
                ]
                if len(occurrences) >= 3:
                    recommendations.append({
                        "timestamp": timestamp,
                        "trigger": "repeated_error",
                        "target": led.get("name"),
                        "suggestion": "Check power/circuit",
                        "confidence": 0.8,
                        "status": "pending",
                    })

        return recommendations


class MlService:
    def __init__(self, config: ServiceConfig) -> None:
        self._config = config
        self._model = DivergenceModel(config.baseline_days, config.zscore_threshold)
        self._stop_requested = False
        self._health = ServiceHealthTracker(config.data_dir)
        self._identity = ServiceIdentity(name="ml_service")

    def request_stop(self, *_: Any) -> None:
        logging.info("Stop requested; finishing current cycle")
        self._stop_requested = True

    def run(self, run_once: bool = False) -> None:
        self._health.mark_running(self._identity)
        while not self._stop_requested:
            start = time.monotonic()
            try:
                self.process_once()
            except Exception:
                logging.exception("ML cycle failed")
                self._health.mark_error(self._identity, "ml cycle failed")
            if run_once:
                break
            elapsed = time.monotonic() - start
            sleep_for = max(0.0, self._config.poll_interval_seconds - elapsed)
            if sleep_for > 0:
                time.sleep(sleep_for)

    def process_once(self) -> None:
        history = self._load_history()
        if not history:
            logging.warning("No history available yet; skipping cycle")
            return
        score = self._model.score(history)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "timestamp": int(time.time()),
            "score": score["score"],
            "level": score["level"],
            "metrics": score["metrics"],
        }
        self._write_output(payload)
        self._health.mark_running(self._identity)

    def _load_history(self) -> Optional[List[Dict[str, Any]]]:
        path = self._config.history_path
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logging.error("Invalid JSON in %s: %s", path, exc)
            return None
        entries = data.get("entries") if isinstance(data, dict) else data
        if not isinstance(entries, list):
            logging.error("history file is not a list")
            return None
        recent_cutoff = time.time() - self._config.history_window_seconds
        filtered = [entry for entry in entries if entry.get("timestamp", 0) >= recent_cutoff]
        return filtered or entries

    def _write_output(self, payload: Dict[str, Any]) -> None:
        path = self._config.output_path
        path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(payload, indent=2)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(serialized, encoding="utf-8")
        tmp.replace(path)
        logging.info("Wrote divergence score %.2f", payload["score"])


def load_service_config(path: Path) -> ServiceConfig:
    if not path.exists():
        print(f"Configuration file not found: {path}", file=sys.stderr)
        sys.exit(1)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return ServiceConfig(
        data_dir=Path(data.get("data_dir", "./data")).expanduser().resolve(),
        canonical_state_filename=data.get("canonical_state_filename", DEFAULT_CANONICAL_FILENAME),
        history_filename=data.get("history_filename", DEFAULT_HISTORY_FILENAME),
        output_filename=data.get("output_filename", DEFAULT_OUTPUT_FILENAME),
        poll_interval_seconds=float(data.get("poll_interval_seconds", 5)),
        history_window_seconds=int(data.get("history_window_seconds", 900)),
        baseline_days=int(data.get("baseline_days", 7)),
        zscore_threshold=float(data.get("zscore_threshold", 2.5)),
        log_level=(data.get("logging", {}) or {}).get("level", "INFO"),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute divergence score from canonical history")
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to YAML config file (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single iteration and exit",
    )
    parser.add_argument(
        "--log-level",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Override configured log level",
    )
    return parser.parse_args()


def configure_logging(level_name: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level_name.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def main() -> None:
    args = parse_args()
    config_path = Path(args.config).expanduser().resolve()
    service_config = load_service_config(config_path)
    log_level = args.log_level or service_config.log_level
    configure_logging(log_level)
    service = MlService(service_config)
    signal.signal(signal.SIGTERM, service.request_stop)
    signal.signal(signal.SIGINT, service.request_stop)
    logging.info("Starting ml_service writing to %s", service_config.output_path)
    service.run(run_once=args.once)


if __name__ == "__main__":
    main()
