import asyncio
from truth_mirror.geo_orchestrator import GeopoliticalPipeline

claims = [
    'The UAE is covertly funding the RSF in Sudan while publicly calling for peace.',
    'France is sending nuclear weapons to Ukraine.',
    "China's economic growth slowed to 4.7% in Q2 2024."
]

async def run():
    pipeline = GeopoliticalPipeline()
    for claim in claims:
        print(f'\nRunning claim: {claim}')
        res = await pipeline.run_async(claim)
        print(f'Done. Verdict: {res.verdict}')

asyncio.run(run())
