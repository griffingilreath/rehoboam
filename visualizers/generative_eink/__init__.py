"""Config-driven generative e-ink visualizer scaffolding."""

from .channel_space import ChannelSpace
from .config import loaders as config_loaders
from .config.models import ChannelDefinition, EntitySpec, VisualizerConfig
from .feature_space import FeatureSpace
from .runtime import VisualizerRuntime
from .types import EntityStateEvent, FeatureSnapshot

__all__ = [
    "ChannelDefinition",
    "ChannelSpace",
    "EntitySpec",
    "FeatureSpace",
    "FeatureSnapshot",
    "VisualizerConfig",
    "VisualizerRuntime",
    "config_loaders",
    "EntityStateEvent",
]
