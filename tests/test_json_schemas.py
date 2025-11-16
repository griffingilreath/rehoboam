"""Validate shared JSON artifacts against their schemas."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft7Validator, RefResolver

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "docs" / "schemas"
SAMPLE_DIR = REPO_ROOT / "samples"

FIXTURES = [
    ("led_config.schema.json", "led_config.sample.json"),
    ("raw_state.schema.json", "raw_state.sample.json"),
    ("canonical_state.schema.json", "canonical_state.sample.json"),
    ("history.schema.json", "history.sample.json"),
    ("divergence.schema.json", "divergence.sample.json"),
    ("service_health.schema.json", "service_health.sample.json"),
]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class SchemaValidationTest(unittest.TestCase):
    def test_samples_match_schema(self) -> None:
        for schema_name, sample_name in FIXTURES:
            with self.subTest(schema=schema_name, sample=sample_name):
                schema_path = SCHEMA_DIR / schema_name
                sample_path = SAMPLE_DIR / sample_name
                self.assertTrue(schema_path.exists(), f"missing schema {schema_path}")
                self.assertTrue(sample_path.exists(), f"missing sample {sample_path}")

                schema = _load_json(schema_path)
                sample = _load_json(sample_path)

                base_uri = f"file://{SCHEMA_DIR.resolve()}/"
                resolver = RefResolver(base_uri=base_uri, referrer=schema)
                validator = Draft7Validator(schema, resolver=resolver)
                errors = sorted(validator.iter_errors(sample), key=lambda e: e.path)
                self.assertFalse(errors, f"{sample_name} failed validation: {[e.message for e in errors]}")
