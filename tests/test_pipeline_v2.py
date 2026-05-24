import pytest
from truth_mirror.orchestrator import TruthMirrorPipeline

CLAIMS = [
    "The Eiffel Tower is located in Paris, France.",
    "Water boils at 100 degrees Celsius at sea level.",
    "William Shakespeare wrote the play Hamlet.",
    "The Great Wall of China is visible from space with the naked eye.",
    "Albert Einstein won the Nobel Prize for his theory of relativity.",
    "There are 8 planets in the solar system.",
    "Human DNA is 50% identical to bananas."
]

def test_pipeline_with_claims():
    pipeline = TruthMirrorPipeline()
    for claim in CLAIMS:
        result = pipeline.verify(claim)
        assert result.original_claim == claim
        assert result.final_verdict in ["Supported", "Partially supported", "Contradicted", "Unsupported", "Unclear"]
