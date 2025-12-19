#!/usr/bin/env python3
"""Skeleton ML service that computes simple divergence scores."""
from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from jetson.common.json_store import atomic_write_json
from jetson.common.service_health import ServiceHealthTracker, ServiceIdentity
from jetson.common.service_runner import RunnerOverrides, run_service
from jetson.common.utils import wait_for_next_cycle


DEFAULT_CONFIG_PATH = "jetson/ml_service/config.yaml"
DEFAULT_CANONICAL_FILENAME = "canonical_state.json"
DEFAULT_HISTORY_FILENAME = "history.json"
DEFAULT_OUTPUT_FILENAME = "divergence.json"
DEFAULT_FEEDBACK_FILENAME = "feedback.json"
DEFAULT_FEATURES_FILENAME = "features.json"
DIVERGENCE_SCHEMA_VERSION = "1.0"
RECOMMENDATIONS_STATE_SCHEMA_VERSION = "1.0"
FEATURES_SCHEMA_VERSION = "1.0"


default_metrics = [
    "active_leds",
    "active_ratio",
    "avg_activity",
    "max_activity",
    "p95_activity",
    "error_count",
    "error_ratio",
    "warning_count",
    "unknown_count",
]


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
    baseline_bucket: str = "global"  # "global" | "daypart"
    baseline_method: str = "standard"  # "standard" (mean/pstdev) | "robust" (median/MAD)
    score_method: str = "max"  # "max" | "weighted_mean"
    zscore_cap: float = 10.0
    metric_weights: Dict[str, float] | None = None
    recommendations_enabled: bool = True
    rules_path: Path | None = None
    recommendations_state_filename: str = "recommendations_state.json"
    features_enabled: bool = False
    features_output_filename: str = DEFAULT_FEATURES_FILENAME
    features_max_entries: int = 5000
    model_enabled: bool = False
    model_type: str = "isolation_forest"
    model_path: Path | None = None
    model_metadata_path: Path | None = None
    feedback_filename: str = DEFAULT_FEEDBACK_FILENAME
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

    @property
    def feedback_path(self) -> Path:
        return self.data_dir / self.feedback_filename

    @property
    def recommendations_state_path(self) -> Path:
        return self.data_dir / self.recommendations_state_filename

    @property
    def features_path(self) -> Path:
        return self.data_dir / self.features_output_filename


class DivergenceModel:
    """Very simple z-score based divergence calculator."""

    def __init__(
        self,
        baseline_days: int,
        threshold: float,
        *,
        baseline_bucket: str = "global",
        baseline_method: str = "standard",
        score_method: str = "max",
        zscore_cap: float = 10.0,
        metric_weights: Dict[str, float] | None = None,
    ) -> None:
        self._baseline_days = max(1, baseline_days)
        self._threshold = threshold
        # Cache for baseline metrics to avoid re-computing on every cycle if history is large
        self._baseline_cache: Tuple[float, Dict[str, tuple[float, float]]] | None = None
        self._cache_ttl = 300.0  # 5 minutes
        self._baseline_bucket = (baseline_bucket or "global").lower()
        self._baseline_method = (baseline_method or "standard").lower()
        self._score_method = (score_method or "max").lower()
        self._zscore_cap = float(zscore_cap) if zscore_cap is not None else 0.0
        self._metric_weights = metric_weights or {}

    def score(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not history:
            return {"score": 0.0, "level": "unknown"}
        latest = history[-1]
        metrics = self._extract_metrics(latest)
        baseline = self._get_cached_baseline(history, latest)
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
        composite_score = self._compose_score(scores, fallback=max_z)
        level = "normal"
        if composite_score >= self._threshold:
            level = "divergent"
        elif composite_score >= self._threshold * 0.5:
            level = "caution"
        return {
            "score": round(composite_score, 3),
            "level": level,
            "metrics": scores,
            "score_max_z": round(max_z, 3),
            "scoring": {
                "method": self._score_method,
                "threshold": self._threshold,
                "zscore_cap": self._zscore_cap,
                "metric_weights": self._metric_weights,
            },
            "baseline": {
                "bucket": self._baseline_bucket,
                "method": self._baseline_method,
                "baseline_days": self._baseline_days,
            },
        }

    def _compose_score(self, scores: Dict[str, Dict[str, float]], *, fallback: float) -> float:
        """Compose a single score from per-metric z-scores."""
        if self._score_method not in {"weighted_mean", "weighted"}:
            return float(fallback)
        total = 0.0
        weight_sum = 0.0
        for key, entry in scores.items():
            weight = float(self._metric_weights.get(key, 1.0))
            if weight <= 0:
                continue
            z = float(entry.get("z", 0.0))
            if self._zscore_cap and self._zscore_cap > 0:
                z = min(z, self._zscore_cap)
            total += weight * z
            weight_sum += weight
        if weight_sum <= 1e-9:
            return float(fallback)
        return total / weight_sum

    def _get_cached_baseline(self, history: List[Dict[str, Any]], latest: Dict[str, Any]) -> Dict[str, tuple[float, float]]:
        now = time.time()
        if self._baseline_cache:
            timestamp, baseline = self._baseline_cache
            if now - timestamp < self._cache_ttl:
                return baseline
        baseline = self._compute_baseline(history, latest)
        self._baseline_cache = (now, baseline)
        return baseline

    def _extract_metrics(self, entry: Dict[str, Any]) -> Dict[str, float]:
        leds = entry.get("leds", [])
        led_count = max(len(leds), 1)
        activities = [float(led.get("activity_level", 0.0) or 0.0) for led in leds]
        active_leds = sum(1 for value in activities if value > 0.3)
        avg_activity = sum(activities) / led_count
        max_activity = max(activities, default=0.0)
        p95_activity = self._percentile(activities, 0.95)

        error_count = sum(1 for led in leds if (led.get("health") or "").upper() == "ERROR")
        warning_count = sum(1 for led in leds if (led.get("health") or "").upper() == "WARNING")
        unknown_count = sum(1 for led in leds if (led.get("health") or "").upper() == "UNKNOWN")
        return {
            "active_leds": active_leds,
            "active_ratio": active_leds / led_count,
            "avg_activity": avg_activity,
            "max_activity": max_activity,
            "p95_activity": p95_activity,
            "error_count": error_count,
            "error_ratio": error_count / led_count,
            "warning_count": warning_count,
            "unknown_count": unknown_count,
        }

    @staticmethod
    def _percentile(values: List[float], q: float) -> float:
        """Compute a simple nearest-rank percentile for small lists."""
        if not values:
            return 0.0
        q = min(1.0, max(0.0, q))
        ordered = sorted(values)
        idx = int(round(q * (len(ordered) - 1)))
        return float(ordered[idx])

    def _compute_baseline(
        self,
        history: List[Dict[str, Any]],
        latest: Dict[str, Any],
    ) -> Dict[str, tuple[float, float]]:
        metrics_series: Dict[str, List[float]] = {key: [] for key in default_metrics}
        cutoff = history[-1]["timestamp"] - self._baseline_days * 86400
        recent = [entry for entry in history if entry.get("timestamp", 0) >= cutoff]
        entries = self._select_baseline_entries(recent or history, latest)
        for entry in entries:
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
                baseline[key] = self._compute_location_scale(series)
        return baseline

    def _select_baseline_entries(self, candidates: List[Dict[str, Any]], latest: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Optionally bucket baselines (e.g., compare evening to evening)."""
        if self._baseline_bucket != "daypart":
            return candidates
        latest_daypart = (latest.get("context") or {}).get("daypart")
        if not latest_daypart:
            return candidates
        bucketed = [
            entry
            for entry in candidates
            if (entry.get("context") or {}).get("daypart") == latest_daypart
        ]
        # Guardrail: if we don't have enough bucketed samples, fall back to global.
        return bucketed if len(bucketed) >= 5 else candidates

    def _compute_location_scale(self, series: List[float]) -> tuple[float, float]:
        """Return (mean, stdev) or robust equivalents depending on config."""
        if self._baseline_method == "robust":
            med = statistics.median(series)
            abs_devs = [abs(value - med) for value in series]
            mad = statistics.median(abs_devs)
            # 1.4826 * MAD approximates stdev for normal distributions.
            scale = 1.4826 * mad
            return float(med), float(scale)
        return float(statistics.mean(series)), float(statistics.pstdev(series))

class RecommendationEngine:
    """YAML-driven recommendation rules (deterministic + explainable)."""

    def __init__(self, *, enabled: bool, rules_path: Path | None) -> None:
        self._enabled = enabled
        self._rules_path = rules_path
        self._rules: List[Dict[str, Any]] = self._load_rules(rules_path) if enabled else []

    @staticmethod
    def _load_rules(path: Path | None) -> List[Dict[str, Any]]:
        if not path:
            return []
        if not path.exists():
            logging.warning("Rules file not found: %s", path)
            return []
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:  # pragma: no cover - config read failure
            logging.warning("Unable to read rules file %s: %s", path, exc)
            return []
        rules = data.get("rules") if isinstance(data, dict) else None
        if not isinstance(rules, list):
            logging.warning("Rules file %s does not contain a 'rules' list", path)
            return []
        return [rule for rule in rules if isinstance(rule, dict)]

    def generate(
        self,
        *,
        latest: Dict[str, Any],
        history: List[Dict[str, Any]],
        metrics: Dict[str, Dict[str, float]] | None = None,
    ) -> List[Dict[str, Any]]:
        if not self._enabled or not self._rules:
            return []
        metrics = metrics or {}
        leds = latest.get("leds", []) or []
        timestamp = int(latest.get("timestamp") or time.time())
        context = latest.get("context") or {}
        flags = context.get("flags") or {}

        recs: List[Dict[str, Any]] = []
        for rule in self._rules:
            rule_id = str(rule.get("id") or rule.get("name") or "rule").strip()
            rule_type = str(rule.get("type") or "").strip().lower()
            suggestion = str(rule.get("suggestion") or "").strip()
            if not suggestion:
                continue
            confidence = float(rule.get("confidence", 0.7))
            priority = int(rule.get("priority", 0))
            cooldown_seconds = int(rule.get("cooldown_seconds", 0) or 0)

            if rule_type == "flag_true":
                flag_name = str(rule.get("flag") or "").strip()
                if not flag_name:
                    continue
                # Prefer canonical flags but keep backward compatibility with older context shapes.
                flag_value = flags.get(flag_name)
                if flag_value is None:
                    flag_value = context.get(flag_name)
                if flag_value is not True:
                    continue

                target_type = rule.get("target_type")
                matched = [led for led in leds if target_type and (led.get("type") == target_type)]
                trigger = f"flag_true:{flag_name}"
                if matched:
                    for led in matched:
                        target = led.get("name") or f"LED {led.get('index', '?')}"
                        recs.append(self._make_rec(
                            rec_id=f"{rule_id}:{target}",
                            timestamp=timestamp,
                            trigger=trigger,
                            target=target,
                            suggestion=suggestion,
                            confidence=confidence,
                            priority=priority,
                            cooldown_seconds=cooldown_seconds,
                        ))
                else:
                    recs.append(self._make_rec(
                        rec_id=rule_id,
                        timestamp=timestamp,
                        trigger=trigger,
                        target=str(rule.get("target") or "system"),
                        suggestion=suggestion,
                        confidence=confidence,
                        priority=priority,
                        cooldown_seconds=cooldown_seconds,
                    ))
                continue

            if rule_type == "repeated_error":
                window = int(rule.get("window_entries", 10))
                min_occurrences = int(rule.get("min_occurrences", 3))
                trigger = "repeated_error"
                recent = history[-window:] if window > 0 else history
                for led in leds:
                    if (led.get("health") or "").upper() != "ERROR":
                        continue
                    target = led.get("name") or f"LED {led.get('index', '?')}"
                    occurrences = [
                        entry
                        for entry in recent
                        if any(
                            (entry_led.get("name") == target and (entry_led.get("health") or "").upper() == "ERROR")
                            for entry_led in (entry.get("leds") or [])
                        )
                    ]
                    if len(occurrences) >= min_occurrences:
                        recs.append(self._make_rec(
                            rec_id=f"{rule_id}:{target}",
                            timestamp=timestamp,
                            trigger=trigger,
                            target=target,
                            suggestion=suggestion,
                            confidence=confidence,
                            priority=priority,
                            cooldown_seconds=cooldown_seconds,
                        ))
                continue

            if rule_type == "metric_threshold":
                metric_name = str(rule.get("metric") or "").strip()
                if not metric_name:
                    continue
                op = str(rule.get("op") or "gt").strip().lower()
                threshold = float(rule.get("threshold", 0))
                value = float((metrics.get(metric_name) or {}).get("value", 0.0))
                passed = False
                if op in {"gt", "greater_than"}:
                    passed = value > threshold
                elif op in {"gte", "ge"}:
                    passed = value >= threshold
                elif op in {"lt", "less_than"}:
                    passed = value < threshold
                elif op in {"lte", "le"}:
                    passed = value <= threshold
                if not passed:
                    continue
                recs.append(self._make_rec(
                    rec_id=rule_id,
                    timestamp=timestamp,
                    trigger=f"metric_threshold:{metric_name}",
                    target=str(rule.get("target") or "system"),
                    suggestion=suggestion,
                    confidence=confidence,
                    priority=priority,
                    cooldown_seconds=cooldown_seconds,
                    details={"metric": metric_name, "op": op, "threshold": threshold, "value": value},
                ))
                continue

        return recs

    @staticmethod
    def _make_rec(
        *,
        rec_id: str,
        timestamp: int,
        trigger: str,
        target: str,
        suggestion: str,
        confidence: float,
        priority: int,
        cooldown_seconds: int = 0,
        details: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        return {
            "id": rec_id,
            "timestamp": timestamp,
            "trigger": trigger,
            "target": target,
            "suggestion": suggestion,
            "confidence": round(confidence, 3),
            "priority": priority,
            "status": "pending",
            "cooldown_seconds": cooldown_seconds,
            "details": details or {},
        }


class RecommendationStateStore:
    """Persist and apply recommendation status + cooldown to avoid spam."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> Dict[str, Any]:
        if not self._path.exists():
            return {"schema_version": RECOMMENDATIONS_STATE_SCHEMA_VERSION, "items": {}}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"schema_version": RECOMMENDATIONS_STATE_SCHEMA_VERSION, "items": {}}
        if not isinstance(data, dict):
            return {"schema_version": RECOMMENDATIONS_STATE_SCHEMA_VERSION, "items": {}}
        data.setdefault("schema_version", RECOMMENDATIONS_STATE_SCHEMA_VERSION)
        data.setdefault("items", {})
        if not isinstance(data["items"], dict):
            data["items"] = {}
        return data

    def apply(self, recommendations: List[Dict[str, Any]], state: Dict[str, Any], *, now: int) -> List[Dict[str, Any]]:
        items = state.get("items") or {}
        output: List[Dict[str, Any]] = []
        for rec in recommendations:
            rec_id = rec.get("id")
            if not rec_id:
                continue
            entry = items.get(rec_id) if isinstance(items, dict) else None
            if isinstance(entry, dict):
                status = entry.get("status")
                if status in {"applied", "ignored"}:
                    continue
                last_issued = int(entry.get("last_issued", 0) or 0)
                cooldown = int(rec.get("cooldown_seconds", 0) or 0)
                if cooldown > 0 and last_issued > 0 and now - last_issued < cooldown:
                    continue
                if status:
                    rec["status"] = status
            output.append(rec)
        return output

    def record_issued(self, recommendations: List[Dict[str, Any]], state: Dict[str, Any], *, now: int) -> None:
        state.setdefault("schema_version", RECOMMENDATIONS_STATE_SCHEMA_VERSION)
        items = state.setdefault("items", {})
        if not isinstance(items, dict):
            items = {}
            state["items"] = items
        for rec in recommendations:
            rec_id = rec.get("id")
            if not rec_id:
                continue
            entry = items.get(rec_id)
            if not isinstance(entry, dict):
                entry = {}
                items[rec_id] = entry
            entry.setdefault("status", rec.get("status", "pending"))
            entry["last_issued"] = now
        state["updated_at"] = datetime.now(timezone.utc).isoformat()

    def save(self, state: Dict[str, Any]) -> None:
        atomic_write_json(self._path, state)


class FeatureStoreBuilder:
    """Build a lightweight feature store from canonical history."""

    FEATURE_LIST = [
        "active_ratio",
        "avg_activity",
        "p95_activity",
        "max_activity",
        "error_ratio",
        "warning_count",
        "unknown_count",
    ]

    def __init__(self) -> None:
        # DivergenceModel is used here purely as a metric extractor.
        self._metric_extractor = DivergenceModel(baseline_days=1, threshold=9999)

    def build(self, history: List[Dict[str, Any]], *, max_entries: int) -> Dict[str, Any]:
        max_entries = max(1, int(max_entries))
        trimmed = history[-max_entries:]
        rows: List[Dict[str, Any]] = []
        for entry in trimmed:
            vector = self.vector_from_entry(entry)
            context = entry.get("context") or {}
            rows.append({
                "timestamp": int(entry.get("timestamp", 0) or 0),
                "daypart": context.get("daypart"),
                "vector": vector,
            })
        return {
            "schema_version": FEATURES_SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "feature_list": list(self.FEATURE_LIST),
            "entries": rows,
        }

    def vector_from_entry(self, entry: Dict[str, Any]) -> List[float]:
        metrics = self._metric_extractor._extract_metrics(entry)
        return [float(metrics.get(name, 0.0)) for name in self.FEATURE_LIST]


class ModelRunner:
    """Optional trained-model inference (kept behind config flags)."""

    def __init__(
        self,
        *,
        enabled: bool,
        model_type: str,
        model_path: Path | None,
        metadata_path: Path | None,
    ) -> None:
        self._enabled = enabled
        self._type = (model_type or "").lower()
        self._model_path = model_path
        self._metadata_path = metadata_path
        self._loaded_mtime: float | None = None
        self._model: Any = None
        self._metadata: Dict[str, Any] = {}

    def infer(self, vector: List[float]) -> Dict[str, Any]:
        if not self._enabled:
            return {"enabled": False}
        if self._type != "isolation_forest":
            return {"enabled": True, "loaded": False, "error": f"unsupported model_type: {self._type}"}
        if not self._model_path:
            return {"enabled": True, "loaded": False, "error": "model_path not configured"}
        try:
            self._ensure_loaded()
        except Exception as exc:  # pragma: no cover - runtime-only
            return {"enabled": True, "loaded": False, "error": str(exc)}
        if not self._model:
            return {"enabled": True, "loaded": False, "error": "model not loaded"}

        # IsolationForest: lower score_samples => more anomalous. Convert to anomaly score.
        import math

        try:
            score_samples = self._model.score_samples([vector])
            raw = float(score_samples[0])
            anomaly = -raw
        except Exception as exc:  # pragma: no cover - runtime-only
            return {"enabled": True, "loaded": True, "error": f"inference failed: {exc}"}

        thresholds = (self._metadata.get("thresholds") or {}) if isinstance(self._metadata, dict) else {}
        caution = float(thresholds.get("caution", math.inf))
        divergent = float(thresholds.get("divergent", math.inf))
        level = "normal"
        if anomaly >= divergent:
            level = "divergent"
        elif anomaly >= caution:
            level = "caution"

        drift = self._compute_drift(vector)

        return {
            "enabled": True,
            "loaded": True,
            "type": "isolation_forest",
            "score": round(anomaly, 6),
            "level": level,
            "thresholds": thresholds,
            "model_version": self._metadata.get("model_version"),
            "drift": drift,
        }

    def _compute_drift(self, vector: List[float]) -> Dict[str, Any]:
        """Compute a simple drift indicator vs. training stats (max abs z-score)."""
        stats = (self._metadata.get("training_stats") or {}) if isinstance(self._metadata, dict) else {}
        means = stats.get("mean")
        stdevs = stats.get("stdev")
        if not isinstance(means, list) or not isinstance(stdevs, list):
            return {}
        if len(means) != len(vector) or len(stdevs) != len(vector):
            return {}
        max_abs_z = 0.0
        for value, mean, stdev in zip(vector, means, stdevs):
            try:
                stdev_f = float(stdev)
                mean_f = float(mean)
            except (TypeError, ValueError):
                continue
            if stdev_f <= 1e-9:
                continue
            z = abs((float(value) - mean_f) / stdev_f)
            if z > max_abs_z:
                max_abs_z = z
        return {"max_abs_z": round(max_abs_z, 3)}

    def _ensure_loaded(self) -> None:
        path = self._model_path
        if not path or not path.exists():
            raise FileNotFoundError(f"model not found: {path}")
        mtime = path.stat().st_mtime
        if self._model is not None and self._loaded_mtime == mtime:
            return

        # Lazy import so sklearn is optional unless model inference is enabled.
        try:
            import pickle
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"pickle unavailable: {exc}") from exc

        try:
            self._model = pickle.loads(path.read_bytes())
        except ModuleNotFoundError as exc:
            # Common when a model was trained with scikit-learn but inference env lacks it.
            raise RuntimeError(
                f"model dependency missing: {exc}. Install scikit-learn in the runtime environment."
            ) from exc
        self._loaded_mtime = mtime

        if self._metadata_path and self._metadata_path.exists():
            try:
                self._metadata = json.loads(self._metadata_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._metadata = {}


class MlService:
    def __init__(self, config: ServiceConfig) -> None:
        self._config = config
        self._model = DivergenceModel(
            config.baseline_days,
            config.zscore_threshold,
            baseline_bucket=config.baseline_bucket,
            baseline_method=config.baseline_method,
            score_method=config.score_method,
            zscore_cap=config.zscore_cap,
            metric_weights=config.metric_weights,
        )
        self._stop_requested = False
        self._health = ServiceHealthTracker(config.data_dir)
        self._identity = ServiceIdentity(name="ml_service")
        self._recs = RecommendationEngine(enabled=config.recommendations_enabled, rules_path=config.rules_path)
        self._rec_state = RecommendationStateStore(config.recommendations_state_path)
        self._features = FeatureStoreBuilder()
        self._model_runner = ModelRunner(
            enabled=config.model_enabled,
            model_type=config.model_type,
            model_path=config.model_path,
            metadata_path=config.model_metadata_path,
        )

    def request_stop(self, *_: Any) -> None:
        logging.info("Stop requested; finishing current cycle")
        self._stop_requested = True

    def run(self, run_once: bool = False) -> None:
        self._health.mark_running(self._identity)
        while not self._stop_requested:
            start = time.monotonic()
            try:
                self.process_once()
            except Exception as exc:
                logging.exception("ML cycle failed")
                self._health.mark_error(self._identity, f"ml cycle failed: {exc}")
            if run_once:
                break
            wait_for_next_cycle(start, self._config.poll_interval_seconds)

    def process_once(self) -> None:
        history = self._load_history()
        if not history:
            logging.warning("No history available yet; skipping cycle")
            return
        score = self._model.score(history)
        raw_recs = self._recs.generate(latest=history[-1], history=history, metrics=score.get("metrics"))
        now = int(time.time())
        state = self._rec_state.load()
        recommendations = self._rec_state.apply(raw_recs, state, now=now)
        self._rec_state.record_issued(recommendations, state, now=now)
        self._rec_state.save(state)
        if self._config.features_enabled:
            features_payload = self._features.build(history, max_entries=self._config.features_max_entries)
            atomic_write_json(self._config.features_path, features_payload)
        model_info: Dict[str, Any] = {"enabled": False}
        if self._config.model_enabled:
            vector = self._features.vector_from_entry(history[-1])
            model_info = self._model_runner.infer(vector)
        feedback_summary = self._summarize_feedback()
        payload = {
            "schema_version": DIVERGENCE_SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "timestamp": int(time.time()),
            "score": score["score"],
            "level": score["level"],
            "metrics": score["metrics"],
            "recommendations": recommendations,
            "baseline": score.get("baseline", {}),
            "score_max_z": score.get("score_max_z"),
            "scoring": score.get("scoring", {}),
            "model": model_info,
            "feedback_summary": feedback_summary,
        }
        self._write_output(payload)
        self._health.mark_running(self._identity)

    def _summarize_feedback(self) -> Dict[str, Any]:
        path = self._config.feedback_path
        if not path.exists():
            return {"total": 0, "approved": 0, "declined": 0, "snoozed": 0, "by_user": {}}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"total": 0, "approved": 0, "declined": 0, "snoozed": 0, "by_user": {}}
        items = data.get("feedback") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return {"total": 0, "approved": 0, "declined": 0, "snoozed": 0, "by_user": {}}

        counts = {"approved": 0, "declined": 0, "snoozed": 0}
        by_user: Dict[str, Dict[str, int]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            decision = str(item.get("decision") or "")
            if decision not in counts:
                continue
            counts[decision] += 1
            user_id = str(item.get("user_id") or "unknown")
            by_user.setdefault(user_id, {"approved": 0, "declined": 0, "snoozed": 0})
            by_user[user_id][decision] += 1

        total = sum(counts.values())
        return {"total": total, **counts, "by_user": by_user}

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
        atomic_write_json(path, payload)
        logging.info("Wrote divergence score %.2f", payload["score"])


def load_service_config(path: Path, overrides: RunnerOverrides | None = None) -> ServiceConfig:
    if not path.exists():
        print(f"Configuration file not found: {path}", file=sys.stderr)
        sys.exit(1)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    overrides = overrides or RunnerOverrides()
    data_dir = overrides.data_dir or Path(data.get("data_dir", "./data")).expanduser().resolve()
    poll_interval = overrides.poll_interval_seconds or float(data.get("poll_interval_seconds", 5))
    log_level = overrides.log_level or (data.get("logging", {}) or {}).get("level", "INFO")
    rec_cfg = data.get("recommendations") or {}
    features_cfg = data.get("features") or {}
    model_cfg = data.get("model") or {}
    model_path: Path | None = None
    model_metadata_path: Path | None = None
    if isinstance(model_cfg, dict):
        model_file = model_cfg.get("model_path")
        if model_file:
            candidate = Path(str(model_file)).expanduser()
            if not candidate.is_absolute():
                candidate = (path.parent / candidate).resolve()
            model_path = candidate
        meta_file = model_cfg.get("metadata_path")
        if meta_file:
            candidate = Path(str(meta_file)).expanduser()
            if not candidate.is_absolute():
                candidate = (path.parent / candidate).resolve()
            model_metadata_path = candidate
    rules_file = None
    if isinstance(rec_cfg, dict):
        rules_file = rec_cfg.get("rules_file") or rec_cfg.get("rules_path")
    rules_path: Path | None = None
    if rules_file:
        candidate = Path(str(rules_file)).expanduser()
        if not candidate.is_absolute():
            candidate = (path.parent / candidate).resolve()
        rules_path = candidate
    return ServiceConfig(
        data_dir=data_dir,
        canonical_state_filename=data.get("canonical_state_filename", DEFAULT_CANONICAL_FILENAME),
        history_filename=data.get("history_filename", DEFAULT_HISTORY_FILENAME),
        output_filename=data.get("output_filename", DEFAULT_OUTPUT_FILENAME),
        feedback_filename=data.get("feedback_filename", DEFAULT_FEEDBACK_FILENAME),
        poll_interval_seconds=poll_interval,
        history_window_seconds=int(data.get("history_window_seconds", 900)),
        baseline_days=int(data.get("baseline_days", 7)),
        zscore_threshold=float(data.get("zscore_threshold", 2.5)),
        baseline_bucket=str(data.get("baseline_bucket", "global")),
        baseline_method=str(data.get("baseline_method", "standard")),
        score_method=str(data.get("score_method", "max")),
        zscore_cap=float(data.get("zscore_cap", 10.0)),
        metric_weights=(data.get("metric_weights") or None),
        recommendations_enabled=bool(rec_cfg.get("enabled", True)) if isinstance(rec_cfg, dict) else True,
        rules_path=rules_path,
        recommendations_state_filename=str(
            rec_cfg.get("state_filename", "recommendations_state.json")
        )
        if isinstance(rec_cfg, dict)
        else "recommendations_state.json",
        features_enabled=bool(features_cfg.get("enabled", False)) if isinstance(features_cfg, dict) else False,
        features_output_filename=str(features_cfg.get("output_filename", DEFAULT_FEATURES_FILENAME))
        if isinstance(features_cfg, dict)
        else DEFAULT_FEATURES_FILENAME,
        features_max_entries=int(features_cfg.get("max_entries", 5000)) if isinstance(features_cfg, dict) else 5000,
        model_enabled=bool(model_cfg.get("enabled", False)) if isinstance(model_cfg, dict) else False,
        model_type=str(model_cfg.get("type", "isolation_forest")) if isinstance(model_cfg, dict) else "isolation_forest",
        model_path=model_path,
        model_metadata_path=model_metadata_path,
        log_level=log_level,
    )


def main() -> None:
    def _create_service(config: ServiceConfig, _: argparse.Namespace) -> MlService:
        logging.info("ML service writing to %s", config.output_path)
        return MlService(config)

    run_service(
        service_name="ml_service",
        description="Compute divergence score from canonical history",
        default_config_path=DEFAULT_CONFIG_PATH,
        load_config=load_service_config,
        create_service=_create_service,
    )


if __name__ == "__main__":
    main()
