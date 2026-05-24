"""CLI entry point for Truth Mirror claim verification."""

from __future__ import annotations

import json

from truth_mirror import TruthMirrorPipeline


def main() -> None:
    claim = input("Enter a claim to verify: ").strip()
    pipeline = TruthMirrorPipeline()
    result = pipeline.verify(claim)
    print(json.dumps(pipeline.to_json(result), indent=2))


if __name__ == "__main__":
    main()
