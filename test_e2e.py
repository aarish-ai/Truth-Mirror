import asyncio
from truth_mirror.geo_orchestrator import GeopoliticalPipeline

async def main():
    pipeline = GeopoliticalPipeline()
    claim = "North Korea conducted a nuclear weapons test in 2026"
    result = await pipeline.run_async(claim)
    print(f"Perspective groups count: {len(result.perspective_groups)}")

asyncio.run(main())

