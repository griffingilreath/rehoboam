from __future__ import annotations

from typing import Mapping

from .config.models import ChannelDefinition, ChannelTerm


def _apply_curve(curve: str, value: float) -> float:
    value = max(0.0, min(1.0, value))
    if curve == "smoothstep":
        return value * value * (3 - 2 * value)
    if curve == "ease_in":
        return value * value
    if curve == "ease_out":
        return 1 - (1 - value) * (1 - value)
    return value


class ChannelSpace:
    """Computes semantic channel values from normalized feature inputs."""

    def __init__(self, channels: tuple[ChannelDefinition, ...]):
        self._channels = channels

    def evaluate(self, features: Mapping[str, float]) -> dict[str, float]:
        output: dict[str, float] = {}
        for channel in self._channels:
            value = channel.bias
            for term in channel.terms:
                contribution = self._evaluate_term(term, features)
                value += contribution
            lo, hi = channel.clamp
            output[channel.channel_id] = max(lo, min(hi, value))
        return output

    def _evaluate_term(self, term: ChannelTerm, features: Mapping[str, float]) -> float:
        source = features.get(term.feature_id, 0.0)
        curved = _apply_curve(term.curve, source)
        return term.weight * curved
