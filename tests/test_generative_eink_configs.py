import json
from pathlib import Path

from visualizers.generative_eink import VisualizerRuntime, config_loaders

BASE = Path(__file__).resolve().parents[1]
ENTITIES = BASE / "visualizers" / "generative_eink" / "config" / "entities.example.yaml"
CHANNELS = BASE / "visualizers" / "generative_eink" / "config" / "channels.example.yaml"
CHANNEL_SAMPLE = BASE / "samples" / "generative_channels.sample.json"


def test_example_configs_load():
    entities = config_loaders.load_entities(ENTITIES)
    channels = config_loaders.load_channels(CHANNELS)

    assert entities, "entities example should define at least one entity"
    assert channels, "channels example should not be empty"

    feature_ids = {feature.feature_id for spec in entities for feature in spec.features.values()}
    assert "motion_living_recent" in feature_ids
    assert any(channel.channel_id == "house_activity" for channel in channels)


def test_runtime_evaluates_channels():
    config = config_loaders.load_config(ENTITIES, CHANNELS)
    runtime = VisualizerRuntime.from_config(config)

    runtime.set_feature("motion_living_recent", 0.8)
    runtime.set_feature("media_is_playing", 1.0)
    runtime.set_feature("lights_on_ratio", 0.6)
    runtime.set_feature("blinds_open_ratio", 0.7)
    runtime.set_feature("outdoor_lux", 0.5)

    channels = runtime.get_channels()
    assert set(channels) >= {"house_activity", "daylight", "resource_use"}
    assert 0 <= channels["house_activity"] <= 1


def test_channel_sample_is_valid_json():
    payload = json.loads(CHANNEL_SAMPLE.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "timestamp",
        "house_activity",
        "soundscape",
        "daylight",
        "comfort",
        "resource_use",
        "network_health",
        "security_tension",
        "long_term_drift",
    }
    assert required.issubset(payload.keys())
    assert all(isinstance(payload[key], (int, float)) for key in required if key not in {"schema_version", "timestamp"})
