"""Source credibility registry and scoring logic."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from truth_mirror.models import EvidenceItem


@dataclass(slots=True)
class CredibilityRegistry:
    source_type_defaults: dict[str, float]
    publisher_overrides: dict[str, float]
    geo_credibility_overrides: dict[str, float] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str) -> "CredibilityRegistry":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            source_type_defaults=payload.get("source_type_defaults", {}),
            publisher_overrides=payload.get("publisher_overrides", {}),
            geo_credibility_overrides=payload.get("geo_credibility_overrides", {}),
        )

    def score(self, item: EvidenceItem, is_geopolitical: bool = False) -> float:
        pub_key = item.publisher.strip().lower()
        if is_geopolitical and pub_key in self.geo_credibility_overrides:
            return self.geo_credibility_overrides[pub_key]
        if pub_key in self.publisher_overrides:
            return self.publisher_overrides[pub_key]
        return self.source_type_defaults.get(item.source_type, 0.5)


